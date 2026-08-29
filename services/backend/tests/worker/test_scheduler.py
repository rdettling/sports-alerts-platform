from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import CompetitionSetting
from app.services.competitions import ensure_competition_settings, get_competition_profile
from app.worker import scheduler
from app.worker.ingest import CatalogSyncResult, LiveSyncResult


def _job(
    job_type: scheduler.JobType = scheduler.CATALOG_SYNC_JOB,
    competition: str = "MLB",
    next_run_at: datetime | None = None,
) -> scheduler.ScheduledJob:
    return scheduler.ScheduledJob(
        job_type=job_type,
        competition=competition,
        next_run_at=next_run_at or datetime.now(timezone.utc),
    )


def _catalog_result(competition: str = "MLB", **overrides) -> CatalogSyncResult:
    return replace(
        CatalogSyncResult(
            competition=competition,
            games_checked=0,
            games_updated=0,
            alerts_created=0,
            odds_candidates=0,
            odds_snapshots_created=0,
            games_removed=0,
            next_live_sync_at=None,
        ),
        **overrides,
    )


def _live_result(competition: str = "MLB", **overrides) -> LiveSyncResult:
    return replace(
        LiveSyncResult(
            competition=competition,
            games_checked=0,
            games_updated=0,
            alerts_created=0,
            has_live_games=False,
            next_scheduled_start_at=None,
        ),
        **overrides,
    )


def test_sync_jobs_creates_active_competition_jobs():
    now = datetime.now(timezone.utc)
    jobs: scheduler.JobSchedule = {}

    scheduler._sync_jobs(jobs, ["MLB", "NBA"], now)

    assert set(jobs) == {
        ("catalog_sync", "MLB"),
        ("live_sync", "MLB"),
        ("catalog_sync", "NBA"),
        ("live_sync", "NBA"),
    }
    assert all(job.next_run_at == now for job in jobs.values())


def test_sync_jobs_adds_enabled_and_removes_disabled_competitions():
    now = datetime.now(timezone.utc)
    jobs: scheduler.JobSchedule = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")].failure_count = 2

    later = now + timedelta(minutes=5)
    scheduler._sync_jobs(jobs, ["NBA"], later)

    assert set(jobs) == {("catalog_sync", "NBA"), ("live_sync", "NBA")}
    assert all(job.next_run_at == later for job in jobs.values())


def test_load_active_competitions_skips_disabled_competitions(db_session):
    ensure_competition_settings(db_session)
    row = db_session.get(CompetitionSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    active = scheduler._load_active_competitions()

    assert "MLB" not in active
    assert "NBA" in active


def test_next_due_job_prefers_catalog_then_competition_name():
    now = datetime.now(timezone.utc)
    jobs = {
        (scheduler.LIVE_SYNC_JOB, "MLB"): _job(scheduler.LIVE_SYNC_JOB, "MLB", now),
        (scheduler.CATALOG_SYNC_JOB, "NBA"): _job(scheduler.CATALOG_SYNC_JOB, "NBA", now),
        (scheduler.CATALOG_SYNC_JOB, "MLB"): _job(scheduler.CATALOG_SYNC_JOB, "MLB", now),
    }

    due = scheduler._next_due_job(jobs, now)

    assert due is jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")]


def test_next_due_job_and_sleep_handle_future_and_empty_schedules(monkeypatch):
    monkeypatch.setattr(scheduler, "SCHEDULER_IDLE_MAX_SLEEP_SECONDS", 120)
    now = datetime.now(timezone.utc)
    jobs = {
        (scheduler.CATALOG_SYNC_JOB, "MLB"): _job(
            scheduler.CATALOG_SYNC_JOB,
            "MLB",
            now + timedelta(minutes=5),
        )
    }

    assert scheduler._next_due_job(jobs, now) is None
    assert scheduler._next_due_seconds(jobs, now) == 120
    assert scheduler._next_due_seconds({}, now) == 120
    assert scheduler._next_due_seconds(jobs, now + timedelta(minutes=5)) == 0


def test_mark_job_success_resets_failures_and_schedules_next_run():
    now = datetime.now(timezone.utc)
    job = _job()
    job.failure_count = 3

    scheduler._mark_job_success(job, 90, now)

    assert job.failure_count == 0
    assert job.next_run_at == now + timedelta(seconds=90)


def test_mark_job_failed_applies_exponential_backoff_with_cap(monkeypatch):
    monkeypatch.setattr(scheduler, "JOB_RETRY_BASE_SECONDS", 30)
    monkeypatch.setattr(scheduler, "JOB_RETRY_MAX_BACKOFF_SECONDS", 60)
    now = datetime.now(timezone.utc)
    job = _job()

    assert scheduler._mark_job_failed(job, now) == 30
    assert job.next_run_at == now + timedelta(seconds=30)
    assert scheduler._mark_job_failed(job, now) == 60
    assert scheduler._mark_job_failed(job, now) == 60
    assert job.failure_count == 3


def test_run_logs_failure_and_stops_after_requested_iteration(monkeypatch, caplog):
    class OneIteration:
        checks = 0

        def is_set(self):
            self.checks += 1
            return self.checks > 1

        def wait(self, _seconds):
            raise AssertionError("due startup job should not wait")

    now = datetime.now(timezone.utc)
    monkeypatch.setattr(scheduler, "_utcnow", lambda: now)
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB"])
    monkeypatch.setattr(
        scheduler,
        "_run_catalog_sync_job",
        lambda _jobs, _competition: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    with caplog.at_level("INFO", logger="app.worker.scheduler"):
        scheduler.run(OneIteration())

    assert "Job failed job_type=catalog_sync competition=MLB failure_count=1 retry_in_seconds=30" in caplog.text
    assert caplog.text.count("Job failed") == 1
    assert "Scheduler loop stopped" in caplog.text


def test_run_live_sync_job_sleeps_until_next_scheduled_start(monkeypatch):
    target = datetime.now(timezone.utc) + timedelta(minutes=42)
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition, next_scheduled_start_at=target),
    )

    next_seconds, result = scheduler._run_live_sync_job("MLB")

    assert 41 * 60 <= next_seconds <= 42 * 60
    assert scheduler._live_mode(result) == "waiting_for_start"


def test_run_live_sync_job_uses_live_interval_when_start_is_overdue(monkeypatch):
    start = datetime.now(timezone.utc) - timedelta(minutes=5)
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition, next_scheduled_start_at=start),
    )

    next_seconds, _ = scheduler._run_live_sync_job("MLB")

    assert next_seconds == get_competition_profile("MLB").live_sync_interval_seconds


def test_run_live_sync_job_uses_catalog_fallback_when_no_upcoming(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition),
    )

    next_seconds, result = scheduler._run_live_sync_job("MLB")

    assert next_seconds == scheduler.settings.catalog_sync_interval_seconds
    assert scheduler._live_mode(result) == "no_upcoming"


@pytest.mark.parametrize(
    ("competition", "interval"),
    [
        ("FBS", 120),
        ("MLB", 300),
        ("MLS", 180),
        ("LA_LIGA", 180),
        ("PREMIER_LEAGUE", 180),
        ("WORLD_CUP", 180),
    ],
)
def test_run_live_sync_job_uses_competition_live_interval(monkeypatch, competition, interval):
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition, has_live_games=True),
    )

    next_seconds, result = scheduler._run_live_sync_job(competition)

    assert next_seconds == interval
    assert result.competition == competition


def test_run_live_sync_job_preserves_alerts_created(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition, alerts_created=2),
    )

    _, result = scheduler._run_live_sync_job("MLB")

    assert result.alerts_created == 2


def test_run_catalog_sync_job_uses_fixed_cadence_and_pulls_live_forward(monkeypatch):
    target = datetime.now(timezone.utc) + timedelta(minutes=20)
    monkeypatch.setattr(
        scheduler,
        "run_catalog_sync",
        lambda provider, competition: _catalog_result(competition, next_live_sync_at=target),
    )
    called = []

    def fake_pull(jobs, competition, desired):
        called.append((jobs, competition, desired))

    monkeypatch.setattr(scheduler, "_pull_live_sync_forward", fake_pull)

    jobs = {}
    next_seconds, result = scheduler._run_catalog_sync_job(jobs, "MLB")

    assert next_seconds == scheduler.settings.catalog_sync_interval_seconds
    assert called == [(jobs, "MLB", target)]
    assert result.competition == "MLB"


@pytest.mark.parametrize(
    ("runner", "wrapper"),
    [
        ("run_catalog_sync", "_run_catalog_sync_job"),
        ("run_live_sync", "_run_live_sync_job"),
    ],
)
def test_sync_job_wrappers_propagate_failures(monkeypatch, runner, wrapper):
    monkeypatch.setattr(
        scheduler,
        runner,
        lambda provider, competition: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        if wrapper == "_run_catalog_sync_job":
            scheduler._run_catalog_sync_job({}, "MLB")
        else:
            scheduler._run_live_sync_job("MLB")


def test_log_job_success_emits_compact_summary(caplog):
    with caplog.at_level("INFO", logger="app.worker.scheduler"):
        scheduler._log_job_success(
            result=_live_result(
                games_checked=23,
                games_updated=2,
                alerts_created=1,
                has_live_games=True,
            ),
            next_run_seconds=300,
            duration_ms=145,
        )

    assert (
        "Job completed job_type=live_sync competition=MLB duration_ms=145 "
        "next_run_seconds=300 games_checked=23 games_updated=2 alerts_created=1 "
        "has_live_games=True mode=live"
    ) in caplog.text


def test_log_catalog_success_includes_all_job_counts(caplog):
    with caplog.at_level("INFO", logger="app.worker.scheduler"):
        scheduler._log_job_success(
            result=_catalog_result(
                games_checked=12,
                games_updated=3,
                alerts_created=2,
                odds_candidates=4,
                odds_snapshots_created=1,
                games_removed=5,
            ),
            next_run_seconds=43200,
            duration_ms=210,
        )

    assert caplog.text.count("Job completed") == 1
    assert (
        "Job completed job_type=catalog_sync competition=MLB duration_ms=210 next_run_seconds=43200 "
        "games_checked=12 games_updated=3 alerts_created=2 odds_candidates=4 "
        "odds_snapshots_created=1 games_removed=5"
    ) in caplog.text


def test_pull_live_sync_forward_uses_native_hint():
    now = datetime.now(timezone.utc)
    live_job = _job(scheduler.LIVE_SYNC_JOB, "MLB", now + timedelta(hours=6))
    jobs = {(scheduler.LIVE_SYNC_JOB, "MLB"): live_job}
    desired = now + timedelta(minutes=20)

    scheduler._pull_live_sync_forward(jobs, "MLB", desired)

    assert live_job.next_run_at == desired


def test_pull_live_sync_forward_does_not_delay_existing_job():
    now = datetime.now(timezone.utc)
    live_job = _job(scheduler.LIVE_SYNC_JOB, "MLB", now + timedelta(minutes=10))
    jobs = {(scheduler.LIVE_SYNC_JOB, "MLB"): live_job}

    scheduler._pull_live_sync_forward(jobs, "MLB", now + timedelta(hours=1))

    assert live_job.next_run_at == now + timedelta(minutes=10)
