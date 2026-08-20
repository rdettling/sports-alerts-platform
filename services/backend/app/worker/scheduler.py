from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Literal

from app.db.session import SessionLocal
from app.services.competitions import get_active_competitions, get_competition_profile
from app.worker.config import settings
from app.worker.ingest import CatalogSyncResult, LiveSyncResult, run_catalog_sync, run_live_sync
from app.worker.scoreboard import EspnScoreboardClient

logger = logging.getLogger(__name__)
SCHEDULER_IDLE_MAX_SLEEP_SECONDS = max(60, settings.scheduler_idle_max_sleep_seconds)
JOB_RETRY_BASE_SECONDS = 30
JOB_RETRY_MAX_BACKOFF_SECONDS = 3600
JobType = Literal["catalog_sync", "live_sync"]
CATALOG_SYNC_JOB: JobType = "catalog_sync"
LIVE_SYNC_JOB: JobType = "live_sync"
JOB_TYPE_ORDER = {CATALOG_SYNC_JOB: 0, LIVE_SYNC_JOB: 1}


@dataclass
class ScheduledJob:
    job_type: JobType
    competition: str
    next_run_at: datetime
    failure_count: int = 0


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


def _sync_jobs(jobs: JobSchedule, active_competitions: list[str], now: datetime) -> None:
    active = set(active_competitions)
    for key in [key for key in jobs if key[1] not in active]:
        del jobs[key]

    for competition in active_competitions:
        for job_type in (CATALOG_SYNC_JOB, LIVE_SYNC_JOB):
            jobs.setdefault(
                (job_type, competition),
                ScheduledJob(job_type=job_type, competition=competition, next_run_at=now),
            )


def _next_due_job(jobs: JobSchedule, now: datetime) -> ScheduledJob | None:
    due = [job for job in jobs.values() if job.next_run_at <= now]
    if not due:
        return None
    return min(due, key=lambda job: (job.next_run_at, JOB_TYPE_ORDER[job.job_type], job.competition))


def _next_due_seconds(jobs: JobSchedule, now: datetime) -> float:
    if not jobs:
        return float(SCHEDULER_IDLE_MAX_SLEEP_SECONDS)
    delta = min(job.next_run_at for job in jobs.values()) - now
    return max(0.0, min(float(SCHEDULER_IDLE_MAX_SLEEP_SECONDS), delta.total_seconds()))


def _mark_job_success(job: ScheduledJob, next_run_seconds: int, now: datetime) -> None:
    job.failure_count = 0
    job.next_run_at = now + timedelta(seconds=max(1, next_run_seconds))


def _mark_job_failed(job: ScheduledJob, now: datetime) -> int:
    job.failure_count += 1
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


def _run_catalog_sync_job(jobs: JobSchedule, competition: str) -> tuple[int, CatalogSyncResult]:
    provider = EspnScoreboardClient()
    result = run_catalog_sync(provider=provider, competition=competition)
    _pull_live_sync_forward(jobs, result.competition, result.next_live_sync_at)
    return max(1, settings.catalog_sync_interval_seconds), result


def _pull_live_sync_forward(jobs: JobSchedule, competition: str, desired: datetime | None) -> None:
    live_job = jobs.get((LIVE_SYNC_JOB, competition))
    if live_job is None or desired is None:
        return

    desired_utc = desired.astimezone(timezone.utc) if desired.tzinfo else desired.replace(tzinfo=timezone.utc)
    current = live_job.next_run_at if live_job.next_run_at.tzinfo else live_job.next_run_at.replace(tzinfo=timezone.utc)
    if desired_utc < current:
        live_job.next_run_at = desired_utc


def _live_mode(result: LiveSyncResult) -> str:
    if result.has_live_games:
        return "live"
    if result.next_scheduled_start_at is not None:
        return "waiting_for_start"
    return "no_upcoming"


def _run_live_sync_job(competition: str) -> tuple[int, LiveSyncResult]:
    provider = EspnScoreboardClient()
    result = run_live_sync(provider=provider, competition=competition)
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


def run(stop_event: threading.Event) -> None:
    jobs: JobSchedule = {}
    logger.info("Scheduler loop started idle_max_sleep=%ss", SCHEDULER_IDLE_MAX_SLEEP_SECONDS)

    while not stop_event.is_set():
        now = _utcnow()
        _sync_jobs(jobs, _load_active_competitions(), now)
        due_job = _next_due_job(jobs, now)
        if due_job is None:
            stop_event.wait(_next_due_seconds(jobs, now))
            continue

        try:
            started_at = monotonic()
            if due_job.job_type == CATALOG_SYNC_JOB:
                next_run, result = _run_catalog_sync_job(jobs, due_job.competition)
            else:
                next_run, result = _run_live_sync_job(due_job.competition)
            duration_ms = int((monotonic() - started_at) * 1000)
            _log_job_success(
                result=result,
                next_run_seconds=next_run,
                duration_ms=duration_ms,
            )
            _mark_job_success(due_job, next_run, _utcnow())
        except Exception:
            backoff_seconds = _mark_job_failed(due_job, _utcnow())
            logger.exception(
                "Job failed job_type=%s competition=%s failure_count=%s retry_in_seconds=%s",
                due_job.job_type,
                due_job.competition,
                due_job.failure_count,
                backoff_seconds,
            )

    logger.info("Scheduler loop stopped")
