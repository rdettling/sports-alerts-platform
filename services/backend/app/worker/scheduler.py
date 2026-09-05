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
from app.worker import updates
from app.worker.config import settings
from app.worker.ingest import CatalogSyncResult, LiveSyncResult, run_catalog_sync, run_live_sync
from app.worker.scoreboard import EspnScoreboardClient

logger = logging.getLogger(__name__)
JOB_RETRY_BASE_SECONDS = 30
JOB_RETRY_MAX_BACKOFF_SECONDS = 3600
CATALOG_SYNC_JOB: JobType = "catalog_sync"
LIVE_SYNC_JOB: JobType = "live_sync"


@dataclass
class ScheduledJob:
    job_type: JobType
    competition: str
    next_run_at: datetime | None
    failure_count: int = 0
    last_success_at: datetime | None = None
    state: JobState = "awaiting_first_result"


JobSchedule = dict[tuple[JobType, str], ScheduledJob]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _competition_live_interval_seconds(competition: str) -> int:
    return max(1, get_competition_profile(competition).live_sync_interval_seconds)


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
        for job_type in (CATALOG_SYNC_JOB, LIVE_SYNC_JOB):
            jobs.setdefault(
                (job_type, competition),
                ScheduledJob(
                    job_type=job_type, competition=competition,
                    next_run_at=now if job_type == LIVE_SYNC_JOB else None,
                ),
            )

    return previous != set(jobs)


def _queue_catalog_cycle(jobs: JobSchedule, next_catalog_at: datetime, now: datetime) -> datetime:
    interval = timedelta(seconds=max(1, settings.catalog_sync_interval_seconds))
    next_catalog_at += interval * ((now - next_catalog_at) // interval + 1)
    count = 0
    for job in jobs.values():
        if job.job_type == CATALOG_SYNC_JOB:
            job.next_run_at = now
            job.failure_count = 0
            job.state = "queued"
            count += 1
    logger.info("Catalog cycle queued leagues=%s next_catalog_at=%s", count, next_catalog_at.isoformat())
    return next_catalog_at


def _next_due_job(jobs: JobSchedule, now: datetime) -> ScheduledJob | None:
    due = [job for job in jobs.values() if job.next_run_at is not None and job.next_run_at <= now]
    live = []
    for job in due:
        if job.job_type != LIVE_SYNC_JOB:
            continue
        catalog = jobs.get((CATALOG_SYNC_JOB, job.competition))
        # Let startup catalog attempts precede the first live read for that league.
        if (
            job.state == "awaiting_first_result" and not job.failure_count
            and catalog is not None and catalog.state == "queued"
            and catalog.last_success_at is None
        ):
            continue
        live.append(job)
    candidates = live or [job for job in due if job.job_type == CATALOG_SYNC_JOB]
    return min(candidates, key=lambda job: (job.next_run_at, job.competition)) if candidates else None


def _next_due_seconds(jobs: JobSchedule, now: datetime, next_catalog_at: datetime) -> float:
    max_sleep = float(max(1, settings.catalog_sync_interval_seconds))
    next_run = min(
        [next_catalog_at] + [job.next_run_at for job in jobs.values() if job.next_run_at is not None]
    )
    return max(0.0, min(max_sleep, (next_run - now).total_seconds()))


def _mark_job_success(
    job: ScheduledJob, next_run_seconds: int | None, now: datetime, *, state: JobState,
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
    backoff_seconds = min(
        JOB_RETRY_MAX_BACKOFF_SECONDS,
        JOB_RETRY_BASE_SECONDS * (2**retry_power),
    )
    job.next_run_at = now + timedelta(seconds=backoff_seconds)
    return backoff_seconds


def _log_job_success(
    *,
    result: CatalogSyncResult | LiveSyncResult,
    next_run_seconds: int,
    duration_ms: int,
) -> None:
    if isinstance(result, CatalogSyncResult):
        logger.info(
            "Job completed job_type=catalog_sync competition=%s duration_ms=%s next_run_seconds=%s games_checked=%s games_updated=%s alerts_created=%s odds_candidates=%s odds_snapshots_created=%s games_removed=%s",
            result.competition,
            duration_ms,
            next_run_seconds,
            result.games_checked,
            result.games_updated,
            result.alerts_created,
            result.odds_candidates,
            result.odds_snapshots_created,
            result.games_removed,
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
    provider = EspnScoreboardClient()
    result = run_catalog_sync(provider=provider, competition=competition)
    _pull_live_sync_forward(jobs, result.competition, result.next_live_sync_at)
    _notify_game_changes(result)
    return result


def _pull_live_sync_forward(jobs: JobSchedule, competition: str, desired: datetime | None) -> None:
    live_job = jobs.get((LIVE_SYNC_JOB, competition))
    if live_job is None or desired is None:
        return

    desired_utc = desired.astimezone(timezone.utc) if desired.tzinfo else desired.replace(tzinfo=timezone.utc)
    current = live_job.next_run_at if live_job.next_run_at.tzinfo else live_job.next_run_at.replace(tzinfo=timezone.utc)
    if desired_utc < current:
        live_job.next_run_at = desired_utc
        if live_job.state == "no_upcoming":
            live_job.state = "waiting_for_start"


def _live_mode(result: LiveSyncResult) -> JobState:
    if result.has_live_games:
        return "live"
    if result.next_scheduled_start_at is not None:
        return "waiting_for_start"
    return "no_upcoming"


def _run_live_sync_job(competition: str) -> tuple[int, LiveSyncResult]:
    provider = EspnScoreboardClient()
    result = run_live_sync(provider=provider, competition=competition)
    _notify_game_changes(result)
    if result.has_live_games:
        return _competition_live_interval_seconds(competition), result

    if result.next_scheduled_start_at is not None:
        next_scheduled = result.next_scheduled_start_at
        if next_scheduled.tzinfo is None:
            next_scheduled = next_scheduled.replace(tzinfo=timezone.utc)
        seconds_until_start = int((next_scheduled - _utcnow()).total_seconds())
        if seconds_until_start > 0:
            return max(1, seconds_until_start), result
        return _competition_live_interval_seconds(competition), result

    return max(1, settings.catalog_sync_interval_seconds), result


def _notify_game_changes(result: CatalogSyncResult | LiveSyncResult) -> None:
    if isinstance(result, CatalogSyncResult):
        changed = bool(
            result.games_updated or result.odds_snapshots_created or result.games_removed
        )
    else:
        changed = bool(result.games_updated)

    if not changed:
        return

    try:
        updates.notify_games_changed(result.competition)
    except Exception:
        logger.exception(
            "Unexpected live update delivery error competition=%s",
            result.competition,
        )


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
                        next_run_at=job.next_run_at or next_catalog_at,
                        last_success_at=job.last_success_at,
                        state=job.state,
                    )
                    for job in jobs.values()
                ],
            )
        )
    except Exception:
        logger.exception("Unexpected schedule report error")


def run(
    stop_event: threading.Event,
    delivery_wake_event: threading.Event | None = None,
) -> None:
    jobs: JobSchedule = {}
    initial_report = True
    next_catalog_at = _utcnow()
    logger.info("Scheduler loop started idle_max_sleep=%ss", max(1, settings.catalog_sync_interval_seconds))

    while not stop_event.is_set():
        now = _utcnow()
        with database_source("worker:competition_scan"):
            changed = _sync_jobs(jobs, _load_active_competitions(), now)
        if now >= next_catalog_at:
            next_catalog_at = _queue_catalog_cycle(jobs, next_catalog_at, now)
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
                    next_run = None
                else:
                    next_run, result = _run_live_sync_job(due_job.competition)
            if delivery_wake_event is not None and result.alerts_created:
                delivery_wake_event.set()
            completed_at = _utcnow()
            duration_ms = int((monotonic() - started_at) * 1000)
            _log_job_success(
                result=result,
                next_run_seconds=(
                    next_run if next_run is not None
                    else max(0, int((next_catalog_at - completed_at).total_seconds()))
                ),
                duration_ms=duration_ms,
            )
            _mark_job_success(
                due_job, next_run, completed_at,
                state=_live_mode(result) if isinstance(result, LiveSyncResult) else "scheduled",
            )
        except Exception:
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
