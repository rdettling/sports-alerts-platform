from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy import delete, func, select

from app.db.models import Game, WorkerJob
from app.services.leagues import get_active_leagues, get_league_profile
from worker.cleanup import cleanup_games_outside_window
from worker.config import settings
from worker.db import SessionLocal
from worker.ingest import run_catalog_sync, run_live_sync
from worker.scoreboard import EspnScoreboardClient

logger = logging.getLogger(__name__)
SCHEDULER_MAX_SLEEP_SECONDS = settings.scheduler_tick_seconds
SCHEDULER_IDLE_MAX_SLEEP_SECONDS = max(60, settings.scheduler_idle_max_sleep_seconds)
JOB_MAX_RETRIES = 5
JOB_RETRY_BASE_SECONDS = 30
JOB_RETRY_MAX_BACKOFF_SECONDS = 3600
CATALOG_SYNC_JOB = "catalog_sync"
LIVE_SYNC_JOB = "live_sync"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _league_live_interval_seconds(league: str) -> int:
    return max(1, get_league_profile(league).live_sync_interval_seconds)


def _sync_job_targets_disabled_league(job: WorkerJob, active_leagues: set[str]) -> bool:
    return (
        job.job_type in {CATALOG_SYNC_JOB, LIVE_SYNC_JOB}
        and job.league is not None
        and job.league not in active_leagues
    )


def _bootstrap_jobs() -> None:
    db = SessionLocal()
    try:
        now = _utcnow()
        active_leagues = set(get_active_leagues(db))
        disabled_sync_jobs = delete(WorkerJob).where(
            WorkerJob.job_type.in_((CATALOG_SYNC_JOB, LIVE_SYNC_JOB)),
            WorkerJob.league.is_not(None),
        )
        if active_leagues:
            disabled_sync_jobs = disabled_sync_jobs.where(WorkerJob.league.not_in(active_leagues))
        db.execute(disabled_sync_jobs)

        jobs_to_ensure: list[tuple[str, str | None]] = []
        for league in active_leagues:
            jobs_to_ensure.extend(((CATALOG_SYNC_JOB, league), (LIVE_SYNC_JOB, league)))

        for job_type, league in jobs_to_ensure:
            existing = db.scalar(select(WorkerJob).where(WorkerJob.job_type == job_type, WorkerJob.league == league))
            if existing:
                if existing.status == "failed":
                    existing.status = "queued"
                if existing.job_type == CATALOG_SYNC_JOB:
                    # Force one fresh catalog pass on each worker startup.
                    existing.next_run_at = now
                if existing.next_run_at is None:
                    existing.next_run_at = now
                continue
            db.add(
                WorkerJob(
                    job_type=job_type,
                    league=league,
                    status="queued",
                    next_run_at=now,
                    attempt_count=0,
                    max_attempts=JOB_MAX_RETRIES,
                )
            )
        db.commit()
    finally:
        db.close()


def _next_due_job(now: datetime) -> WorkerJob | None:
    db = SessionLocal()
    try:
        active_leagues = set(get_active_leagues(db))
        row = db.scalar(
            select(WorkerJob)
            .where(
                WorkerJob.status == "queued",
                WorkerJob.next_run_at <= now,
            )
            .order_by(WorkerJob.next_run_at.asc(), WorkerJob.id.asc())
            .limit(1)
        )
        if not row:
            return None
        if _sync_job_targets_disabled_league(row, active_leagues):
            db.delete(row)
            db.commit()
            return None
        db.expunge(row)
        return row
    finally:
        db.close()


def _next_due_seconds(now: datetime) -> float:
    db = SessionLocal()
    try:
        active_leagues = set(get_active_leagues(db))
        row = db.scalar(
            select(WorkerJob)
            .where(
                WorkerJob.status == "queued",
                WorkerJob.job_type.in_((CATALOG_SYNC_JOB, LIVE_SYNC_JOB)),
                WorkerJob.league.in_(sorted(active_leagues)),
            )
            .order_by(WorkerJob.next_run_at.asc(), WorkerJob.id.asc())
            .limit(1)
        )
        if not row:
            return float(SCHEDULER_IDLE_MAX_SLEEP_SECONDS)
        delta = (row.next_run_at - now).total_seconds()
        # Let the worker sleep until the next due job instead of wake-polling every
        # scheduler tick; stop_event.wait() still wakes immediately on shutdown.
        return max(0.0, min(float(SCHEDULER_IDLE_MAX_SLEEP_SECONDS), delta))
    finally:
        db.close()


def _mark_job_running(job_id: int, now: datetime) -> None:
    db = SessionLocal()
    try:
        row = db.get(WorkerJob, job_id)
        if row is None:
            return
        row.status = "running"
        row.last_started_at = now
        db.commit()
    finally:
        db.close()


def _mark_job_success(job_id: int, next_run_seconds: int, now: datetime) -> None:
    db = SessionLocal()
    try:
        row = db.get(WorkerJob, job_id)
        if row is None:
            return
        row.status = "queued"
        row.attempt_count = 0
        row.backoff_until = None
        row.last_error = None
        row.last_finished_at = now
        row.next_run_at = now + timedelta(seconds=max(1, next_run_seconds))
        db.commit()
    finally:
        db.close()


def _mark_job_failed(job_id: int, error_message: str, now: datetime) -> None:
    db = SessionLocal()
    try:
        row = db.get(WorkerJob, job_id)
        if row is None:
            return
        row.attempt_count += 1
        row.last_error = error_message[:2000]
        row.last_finished_at = now

        retry_power = max(0, row.attempt_count - 1)
        uncapped_backoff = max(1, JOB_RETRY_BASE_SECONDS) * (2 ** retry_power)
        backoff_seconds = min(max(1, JOB_RETRY_MAX_BACKOFF_SECONDS), uncapped_backoff)
        row.status = "queued"
        row.backoff_until = now + timedelta(seconds=backoff_seconds)
        row.next_run_at = row.backoff_until
        db.commit()
    finally:
        db.close()


def _log_job_success(
    *,
    job_type: str,
    league: str | None,
    result: dict[str, int | str | None],
    next_run_seconds: int,
    duration_ms: int,
) -> None:
    logger.info(
        "Job completed job_type=%s league=%s status=%s duration_ms=%s next_run_seconds=%s games_checked=%s games_updated=%s alerts_created=%s has_live_games=%s mode=%s",
        job_type,
        league,
        result.get("status", "success"),
        duration_ms,
        next_run_seconds,
        result.get("games_checked"),
        result.get("games_updated"),
        result.get("alerts_created"),
        result.get("has_live_games"),
        result.get("mode"),
    )


def _run_catalog_sync_job(league: str) -> tuple[int, dict[str, int | str | None]]:
    provider = EspnScoreboardClient()
    result = run_catalog_sync(provider=provider, league=league)
    if str(result.get("status", "")) != "success":
        raise RuntimeError(str(result.get("error") or f"Catalog sync failed for {league}"))
    db = SessionLocal()
    try:
        removed = cleanup_games_outside_window(db)
        db.commit()
        if removed:
            logger.info("Cleanup removed games=%s", removed)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _pull_live_sync_forward(league)
    fallback = settings.catalog_sync_interval_seconds
    next_poll = int(result.get("next_poll_seconds", fallback))
    return max(1, next_poll), result


def _pull_live_sync_forward(league: str) -> None:
    """Move live-sync earlier when catalog discovers an upcoming/live game."""
    now = _utcnow()
    db = SessionLocal()
    try:
        live_job = db.scalar(
            select(WorkerJob).where(
                WorkerJob.job_type == LIVE_SYNC_JOB,
                WorkerJob.league == league,
            )
        )
        if live_job is None or live_job.status == "running":
            return

        has_live = bool(
            db.scalar(
                select(func.count(Game.id)).where(
                    Game.league == league,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live")),
                )
            )
            or 0
        )
        if has_live:
            desired = now
        else:
            next_scheduled = db.scalar(
                select(func.min(Game.scheduled_start_time)).where(
                    Game.league == league,
                    Game.is_final.is_(False),
                    Game.status == "scheduled",
                    Game.scheduled_start_time >= now,
                )
            )
            if next_scheduled is None:
                return
            desired = next_scheduled if next_scheduled.tzinfo else next_scheduled.replace(tzinfo=timezone.utc)

        current = live_job.next_run_at if live_job.next_run_at.tzinfo else live_job.next_run_at.replace(tzinfo=timezone.utc)
        if desired < current:
            live_job.next_run_at = desired
            live_job.status = "queued"
            db.commit()
    finally:
        db.close()


def _run_live_sync_job(league: str) -> tuple[int, dict[str, int | str | None]]:
    provider = EspnScoreboardClient()
    result = run_live_sync(provider=provider, league=league)
    if str(result.get("status", "")) != "success":
        raise RuntimeError(str(result.get("error") or f"Live sync failed for {league}"))
    has_live_games = str(result.get("has_live_games", "false")).lower() == "true"
    if has_live_games:
        next_poll = int(result.get("next_poll_seconds", _league_live_interval_seconds(league)))
        return max(1, next_poll), result

    mode = str(result.get("mode", "no_upcoming"))
    if mode == "waiting_for_start":
        next_scheduled_raw = result.get("next_scheduled_start_at")
        if isinstance(next_scheduled_raw, str) and next_scheduled_raw:
            try:
                next_scheduled = datetime.fromisoformat(next_scheduled_raw.replace("Z", "+00:00"))
                if next_scheduled.tzinfo is None:
                    next_scheduled = next_scheduled.replace(tzinfo=timezone.utc)
                seconds_until_start = int((next_scheduled - _utcnow()).total_seconds())
                if seconds_until_start > 0:
                    return max(1, seconds_until_start), result
                return _league_live_interval_seconds(league), result
            except ValueError:
                pass
        return _league_live_interval_seconds(league), result

    # no_upcoming or unknown
    next_poll = int(result.get("next_poll_seconds", settings.catalog_sync_interval_seconds))
    return max(1, next_poll), result

def run(stop_event: threading.Event) -> None:
    _bootstrap_jobs()
    logger.info("Scheduler loop started max_sleep=%ss", SCHEDULER_MAX_SLEEP_SECONDS)

    while not stop_event.is_set():
        now = _utcnow()
        due_job = _next_due_job(now)
        if due_job is None:
            stop_event.wait(_next_due_seconds(now))
            continue

        _mark_job_running(due_job.id, now)
        try:
            started_at = monotonic()
            if due_job.job_type == CATALOG_SYNC_JOB:
                next_run, result = _run_catalog_sync_job((due_job.league or "NBA").upper())
            elif due_job.job_type == LIVE_SYNC_JOB:
                next_run, result = _run_live_sync_job((due_job.league or "NBA").upper())
            else:
                raise RuntimeError(f"unsupported job type: {due_job.job_type}")
            duration_ms = int((monotonic() - started_at) * 1000)
            _log_job_success(
                job_type=due_job.job_type,
                league=due_job.league,
                result=result,
                next_run_seconds=next_run,
                duration_ms=duration_ms,
            )
            _mark_job_success(due_job.id, next_run, _utcnow())
        except Exception as exc:  # pragma: no cover - exercised through integration behavior
            logger.exception("Worker job failed job_type=%s", due_job.job_type)
            _mark_job_failed(due_job.id, str(exc), _utcnow())

    logger.info("Scheduler loop stopped")
