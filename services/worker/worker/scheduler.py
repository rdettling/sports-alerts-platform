from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.db.models import Game, WorkerJob
from worker.cleanup import cleanup_games_outside_window
from worker.config import settings
from worker.db import SessionLocal
from worker.delivery import count_pending_alerts, process_pending_alerts
from worker.ingest import run_catalog_sync, run_live_sync
from worker.providers.factory import get_provider

logger = logging.getLogger(__name__)
SCHEDULER_MAX_SLEEP_SECONDS = settings.scheduler_tick_seconds
JOB_MAX_RETRIES = 5
JOB_RETRY_BASE_SECONDS = 30
JOB_RETRY_MAX_BACKOFF_SECONDS = 3600
DELIVERY_EMPTY_BACKOFF_SECONDS = settings.delivery_idle_seconds
DELIVERY_ACTIVE_BACKOFF_SECONDS = settings.delivery_active_seconds
CATALOG_SYNC_JOB = "catalog_sync"
LIVE_SYNC_JOB = "live_sync"
DELIVERY_JOB = "delivery"
CLEANUP_JOB = "cleanup_games"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bootstrap_jobs() -> None:
    db = SessionLocal()
    try:
        now = _utcnow()
        # Cleanup now runs inline with catalog sync; remove legacy standalone jobs.
        db.execute(delete(WorkerJob).where(WorkerJob.job_type == CLEANUP_JOB))
        for job_type, league in (
            (CATALOG_SYNC_JOB, "NBA"),
            (CATALOG_SYNC_JOB, "MLB"),
            (LIVE_SYNC_JOB, "NBA"),
            (LIVE_SYNC_JOB, "MLB"),
            (DELIVERY_JOB, None),
        ):
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
        db.expunge(row)
        return row
    finally:
        db.close()


def _next_due_seconds(now: datetime) -> float:
    db = SessionLocal()
    try:
        row = db.scalar(
            select(WorkerJob)
            .where(WorkerJob.status == "queued")
            .order_by(WorkerJob.next_run_at.asc(), WorkerJob.id.asc())
            .limit(1)
        )
        if not row:
            return float(SCHEDULER_MAX_SLEEP_SECONDS)
        delta = (row.next_run_at - now).total_seconds()
        return max(0.0, min(float(SCHEDULER_MAX_SLEEP_SECONDS), delta))
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


def _run_catalog_sync_job(league: str) -> int:
    provider = get_provider()
    result = run_catalog_sync(provider=provider, league=league)
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
    if str(result.get("status", "")) == "success":
        _pull_live_sync_forward(league)
    fallback = settings.catalog_sync_interval_seconds
    next_poll = int(result.get("next_poll_seconds", fallback))
    return max(1, next_poll)


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


def _run_live_sync_job(league: str) -> int:
    provider = get_provider()
    result = run_live_sync(provider=provider, league=league)
    if int(result.get("alerts_created", 0)) > 0:
        _nudge_delivery_job_now()
    has_live_games = str(result.get("has_live_games", "false")).lower() == "true"
    if has_live_games:
        fallback = settings.nba_live_sync_interval_seconds if league == "NBA" else settings.mlb_live_sync_interval_seconds
        next_poll = int(result.get("next_poll_seconds", fallback))
        return max(1, next_poll)

    mode = str(result.get("mode", "no_upcoming"))
    if mode == "waiting_for_start":
        next_scheduled_raw = result.get("next_scheduled_start_at")
        if isinstance(next_scheduled_raw, str) and next_scheduled_raw:
            try:
                next_scheduled = datetime.fromisoformat(next_scheduled_raw.replace("Z", "+00:00"))
                if next_scheduled.tzinfo is None:
                    next_scheduled = next_scheduled.replace(tzinfo=timezone.utc)
                seconds_until_start = int((next_scheduled - _utcnow()).total_seconds())
                return max(1, seconds_until_start)
            except ValueError:
                pass
        return max(1, settings.live_sync_pregame_retry_seconds)

    # no_upcoming or unknown
    next_poll = int(result.get("next_poll_seconds", settings.catalog_sync_interval_seconds))
    return max(1, next_poll)


def _nudge_delivery_job_now() -> None:
    now = _utcnow()
    db = SessionLocal()
    try:
        row = db.scalar(select(WorkerJob).where(WorkerJob.job_type == DELIVERY_JOB, WorkerJob.league.is_(None)))
        if row is None or row.status == "running":
            return
        row.status = "queued"
        row.next_run_at = now
        db.commit()
    finally:
        db.close()


def _run_delivery_job() -> int:
    db = SessionLocal()
    try:
        sent_count, failed_count = process_pending_alerts(db, ingest_run_id=None)
        db.commit()
        has_activity = (sent_count + failed_count) > 0
        if has_activity:
            return max(1, DELIVERY_ACTIVE_BACKOFF_SECONDS)

        # If queue is empty, sleep longer; if queue has pending, keep short cadence.
        pending_count = count_pending_alerts(db)
        if pending_count > 0:
            return max(1, DELIVERY_ACTIVE_BACKOFF_SECONDS)
        return max(1, DELIVERY_EMPTY_BACKOFF_SECONDS)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
            if due_job.job_type == CATALOG_SYNC_JOB:
                next_run = _run_catalog_sync_job((due_job.league or "NBA").upper())
            elif due_job.job_type == LIVE_SYNC_JOB:
                next_run = _run_live_sync_job((due_job.league or "NBA").upper())
            elif due_job.job_type == DELIVERY_JOB:
                next_run = _run_delivery_job()
            else:
                raise RuntimeError(f"unsupported job type: {due_job.job_type}")
            _mark_job_success(due_job.id, next_run, _utcnow())
        except Exception as exc:  # pragma: no cover - exercised through integration behavior
            logger.exception("Worker job failed job_type=%s", due_job.job_type)
            _mark_job_failed(due_job.id, str(exc), _utcnow())

    logger.info("Scheduler loop stopped")
