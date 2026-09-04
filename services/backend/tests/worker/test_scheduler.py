from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

import pytest

from app.db.models import CompetitionSetting
from app.services.competitions import ensure_competition_settings, get_competition_profile
from app.worker import scheduler
from app.worker.ingest import CatalogSyncResult, LiveSyncResult


@pytest.fixture(autouse=True)
def reports(monkeypatch):
    snapshots = []
    monkeypatch.setattr(scheduler.updates, "notify_schedule", snapshots.append)
    return snapshots


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        start = datetime(2026, 9, 4, tzinfo=timezone.utc)
        now = start
        end = start + timedelta(hours=13)

        def __init__(self):
            self.stop = Event()
            self.waits = []

        def wait(self, seconds):
            assert seconds > 0
            self.waits.append((self.now, seconds))
            if self.now + timedelta(seconds=seconds) >= self.end:
                self.stop.set()
            else:
                self.now += timedelta(seconds=seconds)

    clock = Clock()
    monkeypatch.setattr(scheduler, "_utcnow", lambda: clock.now)
    monkeypatch.setattr(clock.stop, "wait", clock.wait)
    monkeypatch.setattr(scheduler.settings, "catalog_sync_interval_seconds", 43200)
    return clock


def _job(
    job_type: scheduler.JobType = scheduler.CATALOG_SYNC_JOB,
    competition: str = "MLB",
    next_run_at: datetime | None = None,
) -> scheduler.ScheduledJob:
    return scheduler.ScheduledJob(
        job_type=job_type,
        competition=competition,
        next_run_at=next_run_at or datetime.now(timezone.utc),
        state="queued" if job_type == scheduler.CATALOG_SYNC_JOB else "awaiting_first_result",
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
    assert all(job.next_run_at == (now if job.job_type == "live_sync" else None) for job in jobs.values())


def test_sync_jobs_adds_enabled_and_removes_disabled_competitions():
    now = datetime.now(timezone.utc)
    jobs: scheduler.JobSchedule = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")].failure_count = 2

    later = now + timedelta(minutes=5)
    scheduler._sync_jobs(jobs, ["NBA"], later)

    assert set(jobs) == {("catalog_sync", "NBA"), ("live_sync", "NBA")}
    assert jobs[("catalog_sync", "NBA")].next_run_at is None
    assert jobs[("live_sync", "NBA")].next_run_at == later


def test_load_active_competitions_skips_disabled_competitions(db_session):
    ensure_competition_settings(db_session)
    row = db_session.get(CompetitionSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    active = scheduler._load_active_competitions()

    assert "MLB" not in active
    assert "NBA" in active


def test_startup_catalog_precedes_its_first_live_read_with_competition_tiebreak():
    now = datetime.now(timezone.utc)
    jobs = {
        (scheduler.LIVE_SYNC_JOB, "MLB"): _job(scheduler.LIVE_SYNC_JOB, "MLB", now),
        (scheduler.CATALOG_SYNC_JOB, "NBA"): _job(scheduler.CATALOG_SYNC_JOB, "NBA", now),
        (scheduler.CATALOG_SYNC_JOB, "MLB"): _job(scheduler.CATALOG_SYNC_JOB, "MLB", now),
    }

    due = scheduler._next_due_job(jobs, now)

    assert due is jobs[(scheduler.CATALOG_SYNC_JOB, "MLB")]


@pytest.mark.parametrize("due_seconds, expected", [
    (30, 30), (20 * 60, 20 * 60), (9 * 3600, 9 * 3600),
    (24 * 3600, 12 * 3600), (0, 0), (-60, 0),
])
def test_sleep_honors_earlier_jobs_and_caps_at_catalog_interval(monkeypatch, due_seconds, expected):
    monkeypatch.setattr(scheduler.settings, "catalog_sync_interval_seconds", 12 * 3600)
    now = datetime.now(timezone.utc)
    jobs = {
        (scheduler.CATALOG_SYNC_JOB, "MLB"): _job(
            scheduler.CATALOG_SYNC_JOB,
            "MLB",
            now + timedelta(seconds=due_seconds),
        )
    }

    assert scheduler._next_due_seconds(jobs, now, now + timedelta(hours=12)) == expected
    assert scheduler._next_due_seconds({}, now, now + timedelta(hours=12)) == 12 * 3600
    monkeypatch.setattr(scheduler.settings, "catalog_sync_interval_seconds", 6 * 3600)
    assert scheduler._next_due_seconds(jobs, now, now + timedelta(hours=12)) == min(expected, 6 * 3600)
    assert scheduler._next_due_seconds({}, now, now + timedelta(hours=12)) == 6 * 3600


@pytest.mark.parametrize("initial, updated, first_wait", [
    (["MLB"], ["MLB"], 9 * 3600),
    (["MLB"], ["NBA"], 9 * 3600),
    (["MLB"], [], 9 * 3600),
    ([], ["NBA"], 12 * 3600),
])
def test_worker_waits_without_hourly_reads_and_discovers_settings_on_wake(
    monkeypatch, clock, reports, initial, updated, first_wait,
):
    start = clock.start
    clock.end = start + timedelta(seconds=first_wait + 1)
    reads, runs = [], []

    def load():
        reads.append(clock.now)
        return initial if clock.now == start else updated

    def catalog(_jobs, competition):
        runs.append((clock.now, "catalog", competition))
        return _catalog_result(competition)

    def live(competition):
        runs.append((clock.now, "live", competition))
        return 9 * 3600, _live_result(competition)

    monkeypatch.setattr(scheduler, "_load_active_competitions", load)
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", catalog)
    monkeypatch.setattr(scheduler, "_run_live_sync_job", live)

    scheduler.run(clock.stop)

    assert reports[0].reported_at == start
    assert {job.competition for job in reports[0].jobs} == set(initial)
    assert {job.competition for job in reports[-1].jobs} == set(updated)
    assert all(job.state == ("queued" if job.job_type == "catalog_sync" else "awaiting_first_result") for job in reports[0].jobs)
    assert reports[0].next_catalog_at == start + timedelta(hours=12)
    assert len(reports) == 1 + len(runs) + (initial != updated)
    assert clock.waits[0] == (start, first_wait)
    assert reads[0] == start
    assert set(reads) == {start, start + timedelta(seconds=first_wait)}
    assert [(kind, competition) for at, kind, competition in runs if at == start] == [
        (kind, competition) for competition in initial for kind in ("catalog", "live")
    ]
    assert [(kind, competition) for at, kind, competition in runs if at > start] == [
        (kind, competition)
        for competition in updated
        for kind in (("catalog", "live") if first_wait == 12 * 3600 else ("live",))
    ]


def test_shutdown_interrupts_empty_schedule_wait_without_another_read(monkeypatch, caplog):
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_utcnow", lambda: now)
    entered_wait = Event()
    reads, waits = [], []

    class StopEvent(Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            entered_wait.set()
            return super().wait(timeout)

    stop = StopEvent()

    def load():
        reads.append(True)
        return []

    monkeypatch.setattr(scheduler.settings, "catalog_sync_interval_seconds", 12 * 3600)
    monkeypatch.setattr(scheduler, "_load_active_competitions", load)
    thread = Thread(target=scheduler.run, args=(stop,), daemon=True)
    with caplog.at_level("INFO", logger="app.worker.scheduler"):
        thread.start()
        try:
            assert entered_wait.wait(2)
        finally:
            stop.set()
            thread.join(timeout=2)
    assert not thread.is_alive()
    assert reads == [True]
    assert waits == [12 * 3600]
    assert "idle_max_sleep=43200s" in caplog.text
    assert "Scheduler loop stopped" in caplog.text


@pytest.mark.parametrize("job_type, next_seconds, state", [
    (scheduler.CATALOG_SYNC_JOB, None, "scheduled"),
    (scheduler.LIVE_SYNC_JOB, 90, "live"),
    (scheduler.LIVE_SYNC_JOB, 3600, "waiting_for_start"),
    (scheduler.LIVE_SYNC_JOB, 43200, "no_upcoming"),
])
def test_success_updates_timing_and_state_together(job_type, next_seconds, state, reports):
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    job = _job(job_type)
    job.failure_count = 3
    job.state = "retry_scheduled"

    scheduler._mark_job_success(job, next_seconds, now, state=state)

    assert job.failure_count == 0
    assert job.next_run_at == (now + timedelta(seconds=next_seconds) if next_seconds else None)
    assert job.last_success_at == now
    assert job.state == state
    scheduler._report_schedule({(job_type, job.competition): job}, now + timedelta(hours=12))
    assert reports[-1].jobs[0].state == job.state


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
    assert job.state == "retry_scheduled"


def test_run_logs_failure_and_stops_after_requested_iteration(monkeypatch, clock, caplog, reports):
    def fail_catalog(_jobs, _competition):
        clock.stop.set()
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB"])
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", fail_catalog)

    with caplog.at_level("INFO", logger="app.worker.scheduler"):
        scheduler.run(clock.stop)

    assert clock.waits == []
    assert "Job failed job_type=catalog_sync competition=MLB failure_count=1 retry_in_seconds=30" in caplog.text
    assert reports[-1].jobs[0].state == "retry_scheduled"
    assert reports[-1].jobs[0].next_run_at == clock.start + timedelta(seconds=30)
    assert reports[-1].jobs[0].last_success_at is None
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


def test_live_sync_notifies_only_after_changed_result_returns(monkeypatch):
    calls = []

    def run_sync(provider, competition):
        calls.append("sync-returned")
        return _live_result(competition, games_updated=1)

    monkeypatch.setattr(scheduler, "run_live_sync", run_sync)
    monkeypatch.setattr(
        scheduler.updates,
        "notify_games_changed",
        lambda competition: calls.append(("notify", competition)),
    )

    scheduler._run_live_sync_job("MLB")

    assert calls == ["sync-returned", ("notify", "MLB")]


def test_unchanged_live_sync_does_not_notify(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition),
    )
    monkeypatch.setattr(
        scheduler.updates,
        "notify_games_changed",
        lambda competition: (_ for _ in ()).throw(AssertionError("must not notify")),
    )

    scheduler._run_live_sync_job("MLB")


def test_run_catalog_sync_job_pulls_live_forward(monkeypatch):
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
    result = scheduler._run_catalog_sync_job(jobs, "MLB")
    assert called == [(jobs, "MLB", target)]
    assert result.competition == "MLB"


@pytest.mark.parametrize(
    "changes",
    [
        {"games_updated": 1},
        {"odds_snapshots_created": 1},
        {"games_removed": 1},
    ],
)
def test_catalog_sync_notifies_for_visible_game_changes(monkeypatch, changes):
    monkeypatch.setattr(
        scheduler,
        "run_catalog_sync",
        lambda provider, competition: _catalog_result(competition, **changes),
    )
    notified = []
    monkeypatch.setattr(scheduler.updates, "notify_games_changed", notified.append)

    scheduler._run_catalog_sync_job({}, "MLB")

    assert notified == ["MLB"]


def test_notification_failure_does_not_fail_completed_sync(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "run_live_sync",
        lambda provider, competition: _live_result(competition, games_updated=1),
    )
    monkeypatch.setattr(
        scheduler.updates,
        "notify_games_changed",
        lambda competition: (_ for _ in ()).throw(RuntimeError("notification failed")),
    )

    _, result = scheduler._run_live_sync_job("MLB")

    assert result.games_updated == 1


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


@pytest.mark.parametrize("state, result", [
    ("live", _live_result(has_live_games=True)),
    ("waiting_for_start", _live_result(next_scheduled_start_at=datetime(2026, 9, 5, tzinfo=timezone.utc))),
    ("no_upcoming", _live_result()),
])
def test_reports_success_and_preserves_idle_wait_on_delivery_error(monkeypatch, clock, state, result, reports):
    now = clock.start
    clock.end = now + timedelta(seconds=1)
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB"])
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", lambda *args: _catalog_result())
    monkeypatch.setattr(scheduler, "_run_live_sync_job", lambda *args: (32400, result))

    def report(snapshot):
        reports.append(snapshot)
        raise RuntimeError("report delivery broke")

    monkeypatch.setattr(scheduler.updates, "notify_schedule", report)
    scheduler.run(clock.stop)
    assert clock.waits == [(now, 32400)]
    assert len(reports) == 3
    catalog, live = reports[-1].jobs
    assert catalog.next_run_at == now + timedelta(hours=12)
    assert live.next_run_at == now + timedelta(hours=9)
    assert catalog.last_success_at == live.last_success_at == now
    assert catalog.state == "scheduled"
    assert live.state == state


def test_report_contains_catalog_adjustment_and_preserves_last_success_on_failure(monkeypatch, reports):
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_utcnow", lambda: now)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    live = jobs[(scheduler.LIVE_SYNC_JOB, "MLB")]
    scheduler._mark_job_success(live, 43200, now, state="no_upcoming")
    target = now + timedelta(hours=1)
    scheduler._pull_live_sync_forward(jobs, "MLB", target)
    scheduler._report_schedule(jobs, now + timedelta(hours=12))
    assert reports[-1].jobs[1].next_run_at == target
    assert reports[-1].jobs[1].state == "waiting_for_start"
    scheduler._mark_job_failed(live, target)
    scheduler._report_schedule(jobs, now + timedelta(hours=12))
    assert reports[-1].jobs[1].last_success_at == now
    assert reports[-1].jobs[1].next_run_at == target + timedelta(seconds=30)
    assert reports[-1].jobs[1].state == "retry_scheduled"


def test_shared_cycles_do_not_drift_and_live_jobs_interleave(monkeypatch, clock, reports):
    runs = []
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB", "NBA"])

    def catalog(jobs, competition):
        runs.append(("catalog", competition, clock.now))
        clock.now += timedelta(seconds=10 if competition == "MLB" else 20)
        return _catalog_result(competition)

    def live(competition):
        runs.append(("live", competition, clock.now))
        return 43200, _live_result(competition)

    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", catalog)
    monkeypatch.setattr(scheduler, "_run_live_sync_job", live)
    scheduler.run(clock.stop)
    assert [(kind, league) for kind, league, _ in runs[:4]] == [
        ("catalog", "MLB"), ("live", "MLB"), ("catalog", "NBA"), ("live", "NBA"),
    ]
    catalogs = [(league, at) for kind, league, at in runs if kind == "catalog"]
    assert catalogs == [("MLB", clock.start), ("NBA", clock.start + timedelta(seconds=10)),
                        ("MLB", clock.start + timedelta(hours=12)), ("NBA", clock.start + timedelta(hours=12, seconds=10))]
    # MLB's due live job ran between catalog attempts in the second cycle too.
    assert [(kind, league) for kind, league, _ in runs[4:7]] == [
        ("catalog", "MLB"), ("live", "MLB"), ("catalog", "NBA"),
    ]
    assert reports[-1].next_catalog_at == clock.start + timedelta(hours=24)
    normal = [j for j in reports[-1].jobs if j.job_type == "catalog_sync"]
    assert {j.next_run_at for j in normal} == {reports[-1].next_catalog_at}
    assert len({j.last_success_at for j in normal}) == 2


def test_new_league_waits_for_shared_cycle_and_disabled_jobs_are_removed(monkeypatch, clock):
    catalogs, lives = [], []
    def active():
        return ["MLB"] if clock.now < clock.start + timedelta(hours=1) else ["NBA"]
    monkeypatch.setattr(scheduler, "_load_active_competitions", active)
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", lambda jobs, league: (catalogs.append((league, clock.now)) or _catalog_result(league)))
    monkeypatch.setattr(scheduler, "_run_live_sync_job", lambda league: (lives.append((league, clock.now)) or (3600, _live_result(league))))
    scheduler.run(clock.stop)
    assert catalogs == [("MLB", clock.start), ("NBA", clock.start + timedelta(hours=12))]
    assert ("NBA", clock.start + timedelta(hours=1)) in lives
    assert not any(league == "MLB" and at > clock.start for league, at in lives)


def test_catalog_failure_retries_only_that_league_then_rejoins_shared_clock(monkeypatch, clock, reports):
    attempts, lives = [], []
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB", "NBA"])
    def catalog(jobs, league):
        attempts.append((league, clock.now))
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return _catalog_result(league)
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", catalog)
    monkeypatch.setattr(scheduler, "_run_live_sync_job", lambda league: (lives.append(league) or (43200, _live_result(league))))
    scheduler.run(clock.stop)
    assert attempts[:3] == [("MLB", clock.start), ("NBA", clock.start), ("MLB", clock.start + timedelta(seconds=30))]
    assert attempts[3:] == [("MLB", clock.start + timedelta(hours=12)), ("NBA", clock.start + timedelta(hours=12))]
    assert lives[:2] == ["MLB", "NBA"]
    retry = next(snapshot for snapshot in reports if any(j.state == "retry_scheduled" for j in snapshot.jobs))
    assert retry.next_catalog_at == clock.start + timedelta(hours=12)


def test_cycle_replaces_retry_once_preserving_last_success_and_skips_missed_cycles():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    catalog = jobs[("catalog_sync", "MLB")]
    scheduler._mark_job_success(catalog, None, now, state="scheduled")
    scheduler._mark_job_failed(catalog, now + timedelta(hours=35, minutes=59, seconds=50))
    assert catalog.failure_count == 1
    next_cycle = scheduler._queue_catalog_cycle(jobs, now + timedelta(hours=12), now + timedelta(hours=36, seconds=5))
    assert next_cycle == now + timedelta(hours=48)
    assert catalog.failure_count == 0
    assert catalog.state == "queued"
    assert catalog.last_success_at == now
    assert catalog.next_run_at == now + timedelta(hours=36, seconds=5)
    assert len([job for job in jobs.values() if job.job_type == "catalog_sync"]) == 1


def test_idle_catalog_records_do_not_create_a_second_timer():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    jobs = {}
    scheduler._sync_jobs(jobs, ["MLB"], now)
    scheduler._mark_job_success(jobs[("live_sync", "MLB")], 86400, now, state="no_upcoming")
    assert jobs[("catalog_sync", "MLB")].next_run_at is None
    assert scheduler._next_due_job(jobs, now) is None
    assert scheduler._next_due_seconds(jobs, now, now + timedelta(hours=3)) == 10800


def test_long_running_catalog_skips_missed_cycles_without_replaying_them(monkeypatch, clock, reports):
    clock.end = clock.start + timedelta(hours=49)
    attempts = []
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB"])
    def catalog(jobs, league):
        attempts.append(clock.now)
        if len(attempts) == 1:
            clock.now += timedelta(hours=36, seconds=5)
        return _catalog_result(league)
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", catalog)
    monkeypatch.setattr(scheduler, "_run_live_sync_job", lambda league: (86400, _live_result(league)))
    scheduler.run(clock.stop)
    assert attempts == [clock.start, clock.start + timedelta(hours=36, seconds=5), clock.start + timedelta(hours=48)]
    assert reports[-1].next_catalog_at == clock.start + timedelta(hours=60)


def test_regular_cycle_supersedes_retry_deadline(monkeypatch, clock, reports):
    attempts = []
    monkeypatch.setattr(scheduler, "_load_active_competitions", lambda: ["MLB"])
    def catalog(jobs, league):
        attempts.append(clock.now)
        if len(attempts) == 1:
            clock.now = clock.start + timedelta(hours=12, seconds=-10)
            raise RuntimeError("failed just before cycle boundary")
        return _catalog_result(league)
    monkeypatch.setattr(scheduler, "_run_catalog_sync_job", catalog)
    monkeypatch.setattr(scheduler, "_run_live_sync_job", lambda league: (86400, _live_result(league)))
    scheduler.run(clock.stop)
    assert attempts == [clock.start, clock.start + timedelta(hours=12)]
    assert reports[-1].next_catalog_at == clock.start + timedelta(hours=24)
    assert reports[-1].jobs[0].state == "scheduled"
