from datetime import datetime, timedelta, timezone

import pytest

from app.worker import scheduler


def _job(job_type, competition, at, state="scheduled"):
    return scheduler.ScheduledJob(job_type, competition, at, state=state)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 1, 0, tzinfo=timezone.utc), datetime(2026, 9, 1, 6, tzinfo=timezone.utc)),
        (datetime(2026, 9, 1, 5, 59, tzinfo=timezone.utc), datetime(2026, 9, 1, 6, tzinfo=timezone.utc)),
        (datetime(2026, 9, 1, 18, tzinfo=timezone.utc), datetime(2026, 9, 2, 0, tzinfo=timezone.utc)),
    ],
)
def test_catalog_boundaries_are_fixed_utc_slots(now, expected):
    assert scheduler._next_catalog_boundary(now) == expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 9, 1, 0, tzinfo=timezone.utc), datetime(2026, 9, 1, 12, tzinfo=timezone.utc)),
        (datetime(2026, 9, 1, 6, tzinfo=timezone.utc), datetime(2026, 9, 1, 12, tzinfo=timezone.utc)),
        (datetime(2026, 9, 1, 12, tzinfo=timezone.utc), datetime(2026, 9, 2, 0, tzinfo=timezone.utc)),
    ],
)
def test_odds_boundaries_are_midnight_and_noon_utc(now, expected):
    assert scheduler._next_odds_boundary(now) == expected


def test_sync_jobs_creates_and_removes_all_competition_jobs():
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    jobs = {}

    scheduler._sync_jobs(jobs, ["MLB", "NBA"], now)
    scheduler._sync_jobs(jobs, ["NBA"], now + timedelta(minutes=1))

    assert set(jobs) == {
        (scheduler.CATALOG_SYNC_JOB, "NBA"),
        (scheduler.LIVE_SYNC_JOB, "NBA"),
        (scheduler.ODDS_SYNC_JOB, "NBA"),
    }


def test_startup_catalog_cycle_never_arms_odds_jobs():
    now = datetime(2026, 9, 1, 3, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)

    scheduler._queue_catalog_cycle(jobs, now, odds_slot=False)

    assert jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")].next_run_at == now
    assert jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")].odds_after_catalog is False
    assert jobs[(scheduler.ODDS_SYNC_JOB, "MLB")].next_run_at is None


def test_regular_noon_cycle_arms_odds_only_after_catalog(monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    scheduler._queue_catalog_cycle(jobs, now, odds_slot=True)
    monkeypatch.setattr(scheduler.odds_sync, "has_eligible_games", lambda competition, at: True)

    catalog = jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")]
    assert catalog.odds_after_catalog is True
    assert jobs[(scheduler.ODDS_SYNC_JOB, "MLB")].next_run_at is None

    scheduler._schedule_odds_after_catalog(jobs, "MLB", now, odds_slot=True)

    assert jobs[(scheduler.ODDS_SYNC_JOB, "MLB")].next_run_at == now


def test_non_odds_catalog_cycle_schedules_next_noon_sweep(monkeypatch):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    monkeypatch.setattr(scheduler.odds_sync, "has_eligible_games", lambda competition, at: True)

    scheduler._schedule_odds_after_catalog(jobs, "MLB", now, odds_slot=False)

    assert jobs[(scheduler.ODDS_SYNC_JOB, "MLB")].next_run_at == datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def test_no_eligible_games_are_reported_as_no_upcoming(monkeypatch):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    monkeypatch.setattr(scheduler.odds_sync, "has_eligible_games", lambda competition, at: False)

    scheduler._schedule_odds_after_catalog(jobs, "MLB", now, odds_slot=False)

    job = jobs[(scheduler.ODDS_SYNC_JOB, "MLB")]
    assert job.state == "no_upcoming"
    assert job.next_run_at is None


def test_successful_empty_catalog_makes_live_job_dormant(monkeypatch):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    live_job = jobs[(scheduler.LIVE_SYNC_JOB, "MLB")]
    live_job.failure_count = 2
    live_job.state = "retry_scheduled"
    monkeypatch.setattr(
        scheduler,
        "run_catalog_sync",
        lambda **kwargs: scheduler.CatalogSyncResult("MLB", 0, 0, 0, 0, None),
    )

    scheduler._run_catalog_sync_job(jobs, "MLB")

    assert live_job.next_run_at is None
    assert live_job.failure_count == 0
    assert live_job.state == "no_upcoming"
    assert scheduler._next_due_job(jobs, now) is None


def test_catalog_rearms_dormant_live_job():
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    start = now + timedelta(hours=2)
    jobs = {
        (scheduler.LIVE_SYNC_JOB, "MLB"): _job(
            scheduler.LIVE_SYNC_JOB, "MLB", None, "no_upcoming"
        )
    }

    scheduler._reconcile_live_sync(jobs, "MLB", start)

    job = jobs[(scheduler.LIVE_SYNC_JOB, "MLB")]
    assert job.next_run_at == start
    assert job.state == "waiting_for_start"
    assert scheduler._next_due_job(jobs, now) is None
    scheduler._reconcile_live_sync(jobs, "MLB", now)
    assert scheduler._next_due_job(jobs, now) is job


def test_failed_startup_catalog_leaves_existing_games_fallback_armed(monkeypatch):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)

    def fail(**kwargs):
        raise RuntimeError("catalog failed")

    monkeypatch.setattr(scheduler, "run_catalog_sync", fail)

    with pytest.raises(RuntimeError, match="catalog failed"):
        scheduler._run_catalog_sync_job(jobs, "MLB")

    job = jobs[(scheduler.LIVE_SYNC_JOB, "MLB")]
    assert job.next_run_at == now
    assert job.state == "awaiting_first_result"


def test_empty_live_sync_has_no_next_deadline(monkeypatch):
    result = scheduler.LiveSyncResult("MLB", 0, 0, 0, False, None)
    monkeypatch.setattr(scheduler, "run_live_sync", lambda **kwargs: result)

    next_run, returned = scheduler._run_live_sync_job("MLB")

    assert next_run is None
    assert returned is result


@pytest.mark.parametrize(
    ("has_live_games", "next_start", "expected_delay"),
    [
        (True, None, 120),
        (False, timedelta(hours=2), 2 * 3600),
        (False, timedelta(minutes=-1), 120),
    ],
)
def test_live_sync_keeps_active_future_and_overdue_work_scheduled(
    monkeypatch, has_live_games, next_start, expected_delay
):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    scheduled_start = now + next_start if next_start is not None else None
    result = scheduler.LiveSyncResult("MLB", 0, 0, 0, has_live_games, scheduled_start)
    monkeypatch.setattr(scheduler, "_utcnow", lambda: now)
    monkeypatch.setattr(scheduler, "run_live_sync", lambda **kwargs: result)

    next_run, _ = scheduler._run_live_sync_job("MLB")

    assert next_run == expected_delay


def test_schedule_report_preserves_missing_deadlines(monkeypatch):
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    jobs = {
        (scheduler.LIVE_SYNC_JOB, "MLB"): _job(
            scheduler.LIVE_SYNC_JOB, "MLB", None, "no_upcoming"
        )
    }
    reported = []
    monkeypatch.setattr(scheduler.updates, "notify_schedule", reported.append)

    scheduler._report_schedule(jobs, now + timedelta(hours=6))

    assert reported[0].jobs[0].next_run_at is None


def test_live_jobs_take_priority_over_odds_then_catalog(monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    jobs = {
        (scheduler.LIVE_SYNC_JOB, "NBA"): _job(scheduler.LIVE_SYNC_JOB, "NBA", now, "live"),
        (scheduler.ODDS_SYNC_JOB, "MLB"): _job(scheduler.ODDS_SYNC_JOB, "MLB", now),
        (scheduler.CATALOG_SYNC_JOB, "NFL"): _job(scheduler.CATALOG_SYNC_JOB, "NFL", now, "queued"),
    }

    monkeypatch.setattr(scheduler.odds_sync, "next_eligible_start", lambda competition, at: now)
    assert scheduler._next_due_job(jobs, now) is jobs[(scheduler.LIVE_SYNC_JOB, "NBA")]
    jobs[(scheduler.LIVE_SYNC_JOB, "NBA")].next_run_at = now + timedelta(minutes=1)
    assert scheduler._next_due_job(jobs, now) is jobs[(scheduler.ODDS_SYNC_JOB, "MLB")]


def test_same_slot_odds_jobs_prioritize_the_nearest_kickoff(monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    jobs = {
        (scheduler.ODDS_SYNC_JOB, "MLB"): _job(scheduler.ODDS_SYNC_JOB, "MLB", now),
        (scheduler.ODDS_SYNC_JOB, "NBA"): _job(scheduler.ODDS_SYNC_JOB, "NBA", now),
    }
    monkeypatch.setattr(
        scheduler.odds_sync,
        "next_eligible_start",
        lambda competition, at: now + timedelta(hours=4 if competition == "MLB" else 2),
    )

    assert scheduler._next_due_job(jobs, now) is jobs[(scheduler.ODDS_SYNC_JOB, "NBA")]


def test_catalog_retry_does_not_keep_the_odds_slot_marker():
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    job = _job(scheduler.CATALOG_SYNC_JOB, "MLB", now, "queued")
    job.odds_after_catalog = True

    scheduler._mark_job_failed(job, now)
    job.odds_after_catalog = False

    assert job.state == "retry_scheduled"
    assert job.odds_after_catalog is False
    assert job.next_run_at == now + timedelta(seconds=30)


def test_budget_limited_odds_wait_for_next_midnight(monkeypatch):
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    job = jobs[(scheduler.ODDS_SYNC_JOB, "MLB")]
    job.state = "budget_limited"
    job.next_run_at = datetime(2026, 9, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler.odds_sync, "has_eligible_games", lambda competition, at: True)

    scheduler._schedule_odds_after_catalog(jobs, "MLB", now, odds_slot=True)

    assert job.next_run_at == datetime(2026, 9, 2, tzinfo=timezone.utc)
    assert job.state == "budget_limited"


def test_sleep_is_bounded_by_the_next_catalog_boundary():
    now = datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    assert scheduler._next_due_seconds({}, now, now + timedelta(hours=6)) == 6 * 3600
