from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, LeagueSetting, Team, WorkerJob
from app.services.leagues import ensure_league_settings
from worker import scheduler


def test_bootstrap_jobs_creates_sync_and_delivery_jobs(db_session):
    scheduler._bootstrap_jobs()
    jobs = db_session.scalars(select(WorkerJob).order_by(WorkerJob.job_type.asc(), WorkerJob.league.asc())).all()
    assert [(job.job_type, job.league) for job in jobs] == [
        ("catalog_sync", "MLB"),
        ("catalog_sync", "NBA"),
        ("catalog_sync", "WORLD_CUP"),
        ("delivery", None),
        ("live_sync", "MLB"),
        ("live_sync", "NBA"),
        ("live_sync", "WORLD_CUP"),
    ]
    assert all(job.status == "queued" for job in jobs)


def test_bootstrap_jobs_skips_disabled_leagues(db_session):
    ensure_league_settings(db_session)
    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    scheduler._bootstrap_jobs()
    jobs = db_session.scalars(select(WorkerJob).order_by(WorkerJob.job_type.asc(), WorkerJob.league.asc())).all()
    assert [(job.job_type, job.league) for job in jobs] == [
        ("catalog_sync", "NBA"),
        ("catalog_sync", "WORLD_CUP"),
        ("delivery", None),
        ("live_sync", "NBA"),
        ("live_sync", "WORLD_CUP"),
    ]


def test_bootstrap_jobs_removes_stale_disabled_league_jobs(db_session):
    ensure_league_settings(db_session)
    db_session.add_all(
        [
            WorkerJob(job_type="catalog_sync", league="MLB", status="queued", next_run_at=datetime.now(timezone.utc), attempt_count=0, max_attempts=5),
            WorkerJob(job_type="live_sync", league="MLB", status="queued", next_run_at=datetime.now(timezone.utc), attempt_count=0, max_attempts=5),
        ]
    )
    db_session.commit()

    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    scheduler._bootstrap_jobs()

    jobs = db_session.scalars(
        select(WorkerJob).where(WorkerJob.league == "MLB").order_by(WorkerJob.job_type.asc())
    ).all()
    assert jobs == []


def test_bootstrap_jobs_removes_legacy_cleanup_job(db_session):
    db_session.add(
        WorkerJob(
            job_type="cleanup_games",
            league=None,
            status="queued",
            next_run_at=datetime.now(timezone.utc),
            attempt_count=0,
            max_attempts=5,
        )
    )
    db_session.commit()

    scheduler._bootstrap_jobs()
    cleanup_job = db_session.scalar(select(WorkerJob).where(WorkerJob.job_type == "cleanup_games"))
    assert cleanup_job is None


def test_bootstrap_jobs_resets_catalog_next_run_for_existing_jobs(db_session):
    stale = datetime.now(timezone.utc) + timedelta(hours=6)
    db_session.add_all(
        [
            WorkerJob(job_type="catalog_sync", league="MLB", status="queued", next_run_at=stale, attempt_count=0, max_attempts=5),
            WorkerJob(job_type="live_sync", league="MLB", status="queued", next_run_at=stale, attempt_count=0, max_attempts=5),
        ]
    )
    db_session.commit()

    before = datetime.now(timezone.utc)
    scheduler._bootstrap_jobs()
    after = datetime.now(timezone.utc)

    db_session.expire_all()
    catalog = db_session.scalar(select(WorkerJob).where(WorkerJob.job_type == "catalog_sync", WorkerJob.league == "MLB"))
    live = db_session.scalar(select(WorkerJob).where(WorkerJob.job_type == "live_sync", WorkerJob.league == "MLB"))
    assert catalog is not None
    assert live is not None
    assert before <= catalog.next_run_at.replace(tzinfo=timezone.utc) <= after
    assert live.next_run_at.replace(tzinfo=timezone.utc) == stale


def test_next_due_job_discards_disabled_league_sync_jobs(db_session):
    ensure_league_settings(db_session)
    due_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db_session.add(
        WorkerJob(job_type="catalog_sync", league="MLB", status="queued", next_run_at=due_at, attempt_count=0, max_attempts=5)
    )
    db_session.commit()

    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    due_job = scheduler._next_due_job(datetime.now(timezone.utc))
    assert due_job is None
    db_session.expire_all()
    remaining = db_session.scalar(select(WorkerJob).where(WorkerJob.job_type == "catalog_sync", WorkerJob.league == "MLB"))
    assert remaining is None


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
    next_seconds, result = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_DEEP_IDLE_BACKOFF_SECONDS
    assert result["delivery_mode"] == "deep_idle"


def test_run_delivery_job_uses_empty_backoff_when_imminent_game(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    team_a = Team(external_team_id="imminent1", league="NBA", name="Imminent A", abbreviation="IA")
    team_b = Team(external_team_id="imminent2", league="NBA", name="Imminent B", abbreviation="IB")
    db_session.add_all([team_a, team_b])
    db_session.flush()
    db_session.add(
        Game(
            external_game_id="imminent-game-1",
            league="NBA",
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            scheduled_start_time=now + timedelta(minutes=45),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 0)
    next_seconds, result = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_EMPTY_BACKOFF_SECONDS
    assert result["delivery_mode"] == "idle"


def test_run_delivery_job_uses_active_backoff_when_pending(db_session, monkeypatch):
    monkeypatch.setattr("worker.scheduler.process_pending_alerts", lambda db, ingest_run_id=None: (0, 0))
    monkeypatch.setattr("worker.scheduler.count_pending_alerts", lambda db: 5)
    next_seconds, result = scheduler._run_delivery_job()
    assert next_seconds == scheduler.DELIVERY_ACTIVE_BACKOFF_SECONDS
    assert result["delivery_mode"] == "backlog"


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
    next_seconds, result = scheduler._run_live_sync_job("MLB")
    assert 41 * 60 <= next_seconds <= 42 * 60
    assert result["mode"] == "waiting_for_start"


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
    next_seconds, result = scheduler._run_live_sync_job("MLB")
    assert next_seconds == scheduler.settings.live_sync_pregame_retry_seconds
    assert result["mode"] == "waiting_for_start"


def test_run_live_sync_job_uses_pregame_retry_when_start_is_past(monkeypatch):
    target = datetime.now(timezone.utc) - timedelta(minutes=5)
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "false",
            "mode": "waiting_for_start",
            "next_scheduled_start_at": target.isoformat(),
        },
    )
    next_seconds, result = scheduler._run_live_sync_job("MLB")
    assert next_seconds == scheduler.settings.live_sync_pregame_retry_seconds
    assert result["mode"] == "waiting_for_start"


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
    next_seconds, result = scheduler._run_live_sync_job("MLB")
    assert next_seconds == scheduler.settings.catalog_sync_interval_seconds
    assert result["mode"] == "no_upcoming"


def test_run_live_sync_job_uses_world_cup_interval(monkeypatch):
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "true",
            "next_poll_seconds": scheduler.settings.world_cup_live_sync_interval_seconds,
        },
    )

    next_seconds, result = scheduler._run_live_sync_job("WORLD_CUP")
    assert next_seconds == scheduler.settings.world_cup_live_sync_interval_seconds
    assert result["has_live_games"] == "true"


def test_run_live_sync_job_nudges_delivery_when_alerts_created(monkeypatch):
    monkeypatch.setattr(
        "worker.scheduler.run_live_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "alerts_created": 2,
            "has_live_games": "false",
            "mode": "no_upcoming",
            "next_poll_seconds": 123,
        },
    )
    called = {"nudged": 0}
    monkeypatch.setattr("worker.scheduler._nudge_delivery_job_now", lambda: called.__setitem__("nudged", called["nudged"] + 1))

    next_seconds, result = scheduler._run_live_sync_job("MLB")
    assert next_seconds == 123
    assert called["nudged"] == 1
    assert result["alerts_created"] == 2


def test_run_catalog_sync_job_runs_cleanup(monkeypatch):
    monkeypatch.setattr(
        "worker.scheduler.run_catalog_sync",
        lambda provider, league: {
            "status": "success",
            "job_type": "catalog_sync",
            "league": league,
            "next_poll_seconds": 123,
        },
    )
    called = {"cleanup": 0}

    def fake_cleanup(_db):
        called["cleanup"] += 1
        return 0

    monkeypatch.setattr("worker.scheduler.cleanup_games_outside_window", fake_cleanup)
    monkeypatch.setattr("worker.scheduler._pull_live_sync_forward", lambda _league: None)

    next_seconds, result = scheduler._run_catalog_sync_job("MLB")
    assert next_seconds == 123
    assert called["cleanup"] == 1
    assert result["job_type"] == "catalog_sync"


def test_log_job_success_emits_compact_summary(caplog):
    with caplog.at_level("INFO", logger="worker.scheduler"):
        scheduler._log_job_success(
            job_type="live_sync",
            league="MLB",
            result={
                "status": "success",
                "games_checked": 23,
                "games_updated": 2,
                "alerts_created": 1,
                "has_live_games": "true",
                "mode": "live",
            },
            next_run_seconds=300,
            duration_ms=145,
        )

    assert "Job completed job_type=live_sync league=MLB status=success duration_ms=145 next_run_seconds=300 games_checked=23 games_updated=2 alerts_created=1 has_live_games=true mode=live" in caplog.text


def test_pull_live_sync_forward_to_next_scheduled_start(db_session):
    now = datetime.now(timezone.utc)
    team_a = Team(external_team_id="TST1", league="MLB", name="Test Team One", abbreviation="T1")
    team_b = Team(external_team_id="TST2", league="MLB", name="Test Team Two", abbreviation="T2")
    db_session.add_all([team_a, team_b])
    db_session.flush()
    db_session.add(
        Game(
            external_game_id="g1",
            league="MLB",
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            scheduled_start_time=now + timedelta(minutes=20),
            status="scheduled",
            is_final=False,
        )
    )
    live_job = WorkerJob(
        job_type="live_sync",
        league="MLB",
        status="queued",
        next_run_at=now + timedelta(hours=6),
        attempt_count=0,
        max_attempts=5,
    )
    db_session.add(live_job)
    db_session.commit()

    scheduler._pull_live_sync_forward("MLB")

    db_session.expire_all()
    updated = db_session.get(WorkerJob, live_job.id)
    assert updated is not None
    assert updated.next_run_at.replace(tzinfo=timezone.utc) <= (now + timedelta(minutes=20)).replace(tzinfo=timezone.utc)


def test_pull_live_sync_forward_to_now_when_live_exists(db_session):
    now = datetime.now(timezone.utc)
    team_a = Team(external_team_id="TST3", league="MLB", name="Test Team Three", abbreviation="T3")
    team_b = Team(external_team_id="TST4", league="MLB", name="Test Team Four", abbreviation="T4")
    db_session.add_all([team_a, team_b])
    db_session.flush()
    db_session.add(
        Game(
            external_game_id="g2",
            league="MLB",
            home_team_id=team_a.id,
            away_team_id=team_b.id,
            scheduled_start_time=now - timedelta(minutes=10),
            status="in_progress",
            is_final=False,
        )
    )
    live_job = WorkerJob(
        job_type="live_sync",
        league="MLB",
        status="queued",
        next_run_at=now + timedelta(hours=1),
        attempt_count=0,
        max_attempts=5,
    )
    db_session.add(live_job)
    db_session.commit()

    before = datetime.now(timezone.utc)
    scheduler._pull_live_sync_forward("MLB")
    after = datetime.now(timezone.utc)

    db_session.expire_all()
    updated = db_session.get(WorkerJob, live_job.id)
    assert updated is not None
    assert before <= updated.next_run_at.replace(tzinfo=timezone.utc) <= after
