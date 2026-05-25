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
    monkeypatch.setattr(scheduler.settings, "job_retry_base_seconds", 60)
    monkeypatch.setattr(scheduler.settings, "job_retry_max_backoff_seconds", 120)
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
    assert next_seconds == scheduler.settings.delivery_empty_backoff_seconds


def test_run_delivery_job_uses_active_backoff_when_pending(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 5)
    next_seconds = scheduler._run_delivery_job()
    assert next_seconds == scheduler.settings.delivery_active_backoff_seconds


def test_run_delivery_job_uses_live_fast_backoff_within_window(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 0)
    scheduler._delivery_fast_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    next_seconds = scheduler._run_delivery_job()
    assert next_seconds == scheduler.settings.delivery_live_fast_backoff_seconds
