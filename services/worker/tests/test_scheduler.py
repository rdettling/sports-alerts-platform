from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import WorkerJob
from worker import scheduler


def test_bootstrap_jobs_creates_sync_and_delivery_jobs(db_session):
    scheduler._bootstrap_jobs()
    jobs = db_session.scalars(select(WorkerJob).order_by(WorkerJob.job_type.asc(), WorkerJob.league.asc())).all()
    assert [(job.job_type, job.league) for job in jobs] == [
        ("catalog_sync", "MLB"),
        ("catalog_sync", "NBA"),
        ("cleanup_games", None),
        ("delivery", None),
        ("live_sync", "MLB"),
        ("live_sync", "NBA"),
    ]
    assert all(job.status == "queued" for job in jobs)


def test_mark_job_failed_applies_backoff(db_session):
    now = datetime.now(timezone.utc)
    job = WorkerJob(
        job_type="catalog_sync",
        league="NBA",
        status="queued",
        next_run_at=now,
        attempt_count=0,
        max_attempts=3,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    scheduler._mark_job_failed(job.id, "boom", now)

    db_session.expire_all()
    updated = db_session.get(WorkerJob, job.id)
    assert updated is not None
    assert updated.status == "queued"
    assert updated.attempt_count == 1
    assert updated.backoff_until is not None
    min_expected = (now + timedelta(seconds=1)).replace(tzinfo=None)
    assert updated.next_run_at >= min_expected


def test_mark_job_failed_requeues_after_max_attempts(db_session):
    now = datetime.now(timezone.utc)
    job = WorkerJob(
        job_type="delivery",
        status="queued",
        next_run_at=now,
        attempt_count=1,
        max_attempts=2,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    scheduler._mark_job_failed(job.id, "fatal", now)

    db_session.expire_all()
    updated = db_session.get(WorkerJob, job.id)
    assert updated is not None
    assert updated.status == "queued"
    assert updated.attempt_count == 2
    assert updated.backoff_until is not None
    assert updated.next_run_at is not None


def test_mark_job_failed_caps_backoff(db_session, monkeypatch):
    monkeypatch.setattr(scheduler, "JOB_RETRY_BASE_SECONDS", 60)
    monkeypatch.setattr(scheduler, "JOB_RETRY_MAX_BACKOFF_SECONDS", 120)
    now = datetime.now(timezone.utc)
    job = WorkerJob(
        job_type="delivery",
        status="queued",
        next_run_at=now,
        attempt_count=3,
        max_attempts=5,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    scheduler._mark_job_failed(job.id, "still failing", now)

    db_session.expire_all()
    updated = db_session.get(WorkerJob, job.id)
    assert updated is not None
    assert updated.backoff_until is not None
    delta = (updated.backoff_until.replace(tzinfo=timezone.utc) - now).total_seconds()
    assert delta <= 120


def test_run_delivery_job_uses_empty_backoff(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 0)
    next_seconds = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_EMPTY_BACKOFF_SECONDS


def test_run_delivery_job_uses_active_backoff_when_pending(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 5)
    next_seconds = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_ACTIVE_BACKOFF_SECONDS


def test_run_delivery_job_uses_live_fast_backoff_within_window(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 0)
    scheduler._delivery_fast_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    next_seconds = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_LIVE_FAST_BACKOFF_SECONDS


def test_run_live_sync_job_sleeps_until_next_scheduled_start(monkeypatch):
    target = datetime.now(timezone.utc) + timedelta(minutes=42)
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "false",
            "mode": "waiting_for_start",
            "next_scheduled_start_at": target.isoformat(),
            "next_poll_seconds": 1,
        },
    )
    next_seconds = scheduler._run_live_sync_job("MLB")
    assert 41 * 60 <= next_seconds <= 42 * 60


def test_run_live_sync_job_uses_pregame_retry_when_start_missing(monkeypatch):
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "false",
            "mode": "waiting_for_start",
            "next_scheduled_start_at": None,
        },
    )
    next_seconds = scheduler._run_live_sync_job("MLB")
    assert next_seconds == scheduler.settings.live_sync_pregame_retry_seconds


def test_run_live_sync_job_uses_catalog_fallback_when_no_upcoming(monkeypatch):
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "false",
            "mode": "no_upcoming",
            "next_poll_seconds": scheduler.settings.catalog_sync_interval_seconds,
        },
    )
    next_seconds = scheduler._run_live_sync_job("MLB")
    assert next_seconds == scheduler.settings.catalog_sync_interval_seconds
