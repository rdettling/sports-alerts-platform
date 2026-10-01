from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic

from app.db.session import SessionLocal
from app.db.usage import database_source
from app.schemas.schedule import JobState, JobType, ScheduledJobOut, ScheduleSnapshot
from app.services.competitions import get_active_competitions, get_competition_profile
from app.worker import odds_sync, updates
from app.worker.ingest import CatalogSyncResult, LiveSyncResult, run_catalog_sync, run_live_sync
from app.worker.odds_sync import OddsSyncResult, run_odds_sync
from app.worker.scoreboard import EspnScoreboardClient

logger = logging.getLogger(__name__)
JOB_RETRY_BASE_SECONDS = 30
JOB_RETRY_MAX_BACKOFF_SECONDS = 3600
CATALOG_INTERVAL = timedelta(hours=6)
CATALOG_SYNC_JOB: JobType = "catalog_sync"
LIVE_SYNC_JOB: JobType = "live_sync"
ODDS_SYNC_JOB: JobType = "odds_sync"


@dataclass
class ScheduledJob:
    job_type: JobType
    competition: str
    next_run_at: datetime | None
    failure_count: int = 0
    last_success_at: datetime | None = None
    state: JobState = "awaiting_first_result"
    odds_after_catalog: bool = False


JobSchedule = dict[tuple[JobType, str], ScheduledJob]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _competition_live_interval_seconds(competition: str) -> int:
    return max(1, get_competition_profile(competition).live_sync_interval_seconds)


def _next_catalog_boundary(now: datetime) -> datetime:
    at = now.astimezone(timezone.utc)
    base = at.replace(hour=(at.hour // 6) * 6, minute=0, second=0, microsecond=0)
    return base + CATALOG_INTERVAL


def _next_odds_boundary(now: datetime) -> datetime:
    at = now.astimezone(timezone.utc)
    midnight = at.replace(hour=0, minute=0, second=0, microsecond=0)
    noon = midnight + timedelta(hours=12)
    return noon if at < noon else midnight + timedelta(days=1)


def _next_utc_midnight(now: datetime) -> datetime:
    at = now.astimezone(timezone.utc)
    return at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _load_active_competitions() -> list[str]:
    db = SessionLocal()
    try:
        return get_active_competitions(db)
    finally:
        db.close()


def _sync_jobs(jobs: JobSchedule, active_competitions: list[str], now: datetime) -> bool:
    previous = set(jobs)
    active = set(active_competitions)
    for key in [key for key in jobs if key[1] not in active]:
        del jobs[key]
    for competition in active_competitions:
        for job_type in (CATALOG_SYNC_JOB, LIVE_SYNC_JOB, ODDS_SYNC_JOB):
            jobs.setdefault(
                (job_type, competition),
                ScheduledJob(
                    job_type=job_type,
                    competition=competition,
                    next_run_at=now if job_type == LIVE_SYNC_JOB else None,
                ),
            )
    return previous != set(jobs)


def _queue_catalog_cycle(
    jobs: JobSchedule,
    now: datetime,
    *,
    odds_slot: bool,
) -> None:
    count = 0
    for job in jobs.values():
        if job.job_type == CATALOG_SYNC_JOB:
            job.next_run_at = now
            job.failure_count = 0
            job.state = "queued"
            job.odds_after_catalog = odds_slot
            count += 1
    if odds_slot:
        for job in jobs.values():
            if job.job_type != ODDS_SYNC_JOB:
                continue
            if job.state == "budget_limited" and now.hour == 12:
                continue
            job.next_run_at = None
            job.state = "awaiting_first_result"
    logger.info("Catalog cycle queued leagues=%s utc_slot=%s", count, now.isoformat())


def _schedule_odds_after_catalog(
    jobs: JobSchedule,
    competition: str,
    now: datetime,
    *,
    odds_slot: bool,
) -> None:
    job = jobs.get((ODDS_SYNC_JOB, competition))
    if job is None or (job.state == "budget_limited" and now.hour != 0):
        return
    target = now if odds_slot else _next_odds_boundary(now)
    if odds_sync.has_eligible_games(competition, target):
        job.next_run_at = now if odds_slot else target
        job.state = "scheduled"
    else:
        job.next_run_at = None
        job.state = "no_upcoming"


def _next_due_job(jobs: JobSchedule, now: datetime) -> ScheduledJob | None:
    due = [job for job in jobs.values() if job.next_run_at is not None and job.next_run_at <= now]
    live = []
    for job in due:
        if job.job_type != LIVE_SYNC_JOB:
            continue
        catalog = jobs.get((CATALOG_SYNC_JOB, job.competition))
        if (
            job.state == "awaiting_first_result"
            and not job.failure_count
            and catalog is not None
            and catalog.state == "queued"
            and catalog.last_success_at is None
        ):
            continue
        live.append(job)
    odds_due = [job for job in due if job.job_type == ODDS_SYNC_JOB]
    if live:
        return min(live, key=lambda job: (job.next_run_at, job.competition))
    if odds_due:
        return min(
            odds_due,
            key=lambda job: (
                odds_sync.next_eligible_start(job.competition, now)
                or datetime.max.replace(tzinfo=timezone.utc),
                job.competition,
            ),
        )
    catalog_due = [job for job in due if job.job_type == CATALOG_SYNC_JOB]
    return min(catalog_due, key=lambda job: (job.next_run_at, job.competition)) if catalog_due else None


def _next_due_seconds(jobs: JobSchedule, now: datetime, next_catalog_at: datetime) -> float:
    next_run = min([next_catalog_at] + [job.next_run_at for job in jobs.values() if job.next_run_at])
    return max(0.0, min(CATALOG_INTERVAL.total_seconds(), (next_run - now).total_seconds()))


def _mark_job_success(
    job: ScheduledJob,
    next_run_seconds: int | None,
    now: datetime,
    *,
    state: JobState,
) -> None:
    job.failure_count = 0
    job.last_success_at = now
    job.state = state
    job.next_run_at = (
        now + timedelta(seconds=max(1, next_run_seconds)) if next_run_seconds is not None else None
    )


def _mark_job_failed(job: ScheduledJob, now: datetime) -> int:
    job.failure_count += 1
    job.state = "retry_scheduled"
    retry_power = max(0, job.failure_count - 1)
    backoff_seconds = min(JOB_RETRY_MAX_BACKOFF_SECONDS, JOB_RETRY_BASE_SECONDS * (2**retry_power))
    job.next_run_at = now + timedelta(seconds=backoff_seconds)
    return backoff_seconds


def _log_job_success(
    *,
    result: CatalogSyncResult | LiveSyncResult | OddsSyncResult,
    next_run_seconds: int,
    duration_ms: int,
) -> None:
    if isinstance(result, CatalogSyncResult):
        logger.info(
            "Job completed job_type=catalog_sync competition=%s duration_ms=%s next_run_seconds=%s games_checked=%s games_updated=%s alerts_created=%s games_removed=%s",
            result.competition,
            duration_ms,
            next_run_seconds,
            result.games_checked,
            result.games_updated,
            result.alerts_created,
            result.games_removed,
        )
        return
    if isinstance(result, OddsSyncResult):
        logger.info(
            "Job completed job_type=odds_sync competition=%s duration_ms=%s next_run_seconds=%s games_checked=%s odds_snapshots_created=%s budget_limited=%s",
            result.competition,
            duration_ms,
            next_run_seconds,
            result.games_checked,
            result.odds_snapshots_created,
            result.budget_limited,
        )
        return
    logger.info(
        "Job completed job_type=live_sync competition=%s duration_ms=%s next_run_seconds=%s games_checked=%s games_updated=%s alerts_created=%s has_live_games=%s mode=%s",
        result.competition,
        duration_ms,
        next_run_seconds,
        result.games_checked,
        result.games_updated,
        result.alerts_created,
        result.has_live_games,
        _live_mode(result),
    )


def _run_catalog_sync_job(jobs: JobSchedule, competition: str) -> CatalogSyncResult:
    result = run_catalog_sync(provider=EspnScoreboardClient(), competition=competition)
    _reconcile_live_sync(jobs, result.competition, result.next_live_sync_at)
    _notify_game_changes(result)
    return result


def _reconcile_live_sync(jobs: JobSchedule, competition: str, desired: datetime | None) -> None:
    live_job = jobs.get((LIVE_SYNC_JOB, competition))
    if live_job is None:
        return
    live_job.failure_count = 0
    if desired is None:
        live_job.next_run_at = None
        live_job.state = "no_upcoming"
        return
    live_job.next_run_at = (
        desired.astimezone(timezone.utc) if desired.tzinfo else desired.replace(tzinfo=timezone.utc)
    )
    live_job.state = "waiting_for_start"


def _live_mode(result: LiveSyncResult) -> JobState:
    if result.has_live_games:
        return "live"
    if result.next_scheduled_start_at is not None:
        return "waiting_for_start"
    return "no_upcoming"


def _run_live_sync_job(competition: str) -> tuple[int | None, LiveSyncResult]:
    result = run_live_sync(provider=EspnScoreboardClient(), competition=competition)
    _notify_game_changes(result)
    if result.has_live_games:
        return _competition_live_interval_seconds(competition), result
    if result.next_scheduled_start_at is not None:
        start = result.next_scheduled_start_at
        start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        seconds_until_start = int((start - _utcnow()).total_seconds())
        if seconds_until_start > 0:
            return max(1, seconds_until_start), result
        return _competition_live_interval_seconds(competition), result
    return None, result


def _run_odds_sync_job(competition: str, now: datetime) -> OddsSyncResult:
    return run_odds_sync(competition, now)


def _notify_game_changes(result: CatalogSyncResult | LiveSyncResult | OddsSyncResult) -> None:
    changed = (
        bool(result.games_updated or result.games_removed)
        if isinstance(result, CatalogSyncResult)
        else bool(result.games_updated)
        if isinstance(result, LiveSyncResult)
        else bool(result.odds_snapshots_created)
    )
    if not changed:
        return
    try:
        updates.notify_games_changed(result.competition)
    except Exception:
        logger.exception("Unexpected live update delivery error competition=%s", result.competition)


def _report_schedule(jobs: JobSchedule, next_catalog_at: datetime) -> None:
    try:
        updates.notify_schedule(
            ScheduleSnapshot(
                reported_at=_utcnow(),
                next_catalog_at=next_catalog_at,
                jobs=[
                    ScheduledJobOut(
                        competition=job.competition,
                        job_type=job.job_type,
                        next_run_at=job.next_run_at,
                        last_success_at=job.last_success_at,
                        state=job.state,
                    )
                    for job in jobs.values()
                ],
            )
        )
    except Exception:
        logger.exception("Unexpected schedule report error")


def run(stop_event: threading.Event, delivery_wake_event: threading.Event | None = None) -> None:
    jobs: JobSchedule = {}
    initial_report = True
    startup_catalog_pending = True
    next_catalog_at = _next_catalog_boundary(_utcnow())
    logger.info("Scheduler loop started utc_catalog_hours=0,6,12,18")

    while not stop_event.is_set():
        now = _utcnow()
        with database_source("worker:competition_scan"):
            changed = _sync_jobs(jobs, _load_active_competitions(), now)
        if startup_catalog_pending:
            _queue_catalog_cycle(jobs, now, odds_slot=False)
            startup_catalog_pending = False
            changed = True
        elif now >= next_catalog_at:
            cycle_at = next_catalog_at
            _queue_catalog_cycle(jobs, now, odds_slot=cycle_at.hour in {0, 12})
            next_catalog_at = _next_catalog_boundary(now)
            changed = True
        if initial_report or changed:
            _report_schedule(jobs, next_catalog_at)
            initial_report = False

        now = _utcnow()
        due_job = _next_due_job(jobs, now)
        if due_job is None:
            stop_event.wait(_next_due_seconds(jobs, now, next_catalog_at))
            continue

        try:
            started_at = monotonic()
            with database_source(f"worker:{due_job.job_type}:{due_job.competition}"):
                if due_job.job_type == CATALOG_SYNC_JOB:
                    result = _run_catalog_sync_job(jobs, due_job.competition)
                    if due_job.odds_after_catalog:
                        _schedule_odds_after_catalog(jobs, due_job.competition, now, odds_slot=True)
                        due_job.odds_after_catalog = False
                    else:
                        _schedule_odds_after_catalog(jobs, due_job.competition, now, odds_slot=False)
                    next_run = None
                elif due_job.job_type == LIVE_SYNC_JOB:
                    next_run, result = _run_live_sync_job(due_job.competition)
                else:
                    result = _run_odds_sync_job(due_job.competition, now)
                    next_run = (
                        max(1, int((_next_utc_midnight(now) - now).total_seconds()))
                        if result.budget_limited
                        else None
                    )
            if delivery_wake_event is not None and getattr(result, "alerts_created", 0):
                delivery_wake_event.set()
            completed_at = _utcnow()
            duration_ms = int((monotonic() - started_at) * 1000)
            _log_job_success(
                result=result,
                next_run_seconds=next_run or max(0, int((next_catalog_at - completed_at).total_seconds())),
                duration_ms=duration_ms,
            )
            _mark_job_success(
                due_job,
                next_run,
                completed_at,
                state=(
                    _live_mode(result)
                    if isinstance(result, LiveSyncResult)
                    else "budget_limited"
                    if isinstance(result, OddsSyncResult) and result.budget_limited
                    else "no_upcoming"
                    if isinstance(result, OddsSyncResult)
                    else "scheduled"
                ),
            )
        except Exception:
            if due_job.job_type == CATALOG_SYNC_JOB and due_job.odds_after_catalog:
                _schedule_odds_after_catalog(jobs, due_job.competition, now, odds_slot=True)
                due_job.odds_after_catalog = False
            backoff_seconds = _mark_job_failed(due_job, _utcnow())
            logger.exception(
                "Job failed job_type=%s competition=%s failure_count=%s retry_in_seconds=%s",
                due_job.job_type,
                due_job.competition,
                due_job.failure_count,
                backoff_seconds,
            )
        _report_schedule(jobs, next_catalog_at)

    logger.info("Scheduler loop stopped")
