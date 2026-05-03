from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import WorkerJob
from worker.cleanup import cleanup_games_outside_window
from worker.config import settings
from worker.db import SessionLocal
from worker.delivery import count_pending_alerts, process_pending_alerts
from worker.ingest import run_ingest_cycle
from worker.providers.factory import get_provider

logger = logging.getLogger(__name__)

INGEST_JOB = "ingest"
DELIVERY_JOB = "delivery"
CLEANUP_JOB = "cleanup_games"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bootstrap_jobs() -> None:
    db = SessionLocal()
    try:
        now = _utcnow()
        for job_type in (INGEST_JOB, DELIVERY_JOB, CLEANUP_JOB):
            existing = db.scalar(select(WorkerJob).where(WorkerJob.job_type == job_type))
            if existing:
                if existing.status == "failed":
                    existing.status = "queued"
                if existing.next_run_at is None:
                    existing.next_run_at = now
                continue
            db.add(
                WorkerJob(
                    job_type=job_type,
                    status="queued",
                    next_run_at=now,
                    attempt_count=0,
                    max_attempts=settings.job_max_retries,
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
            return float(settings.scheduler_max_sleep_seconds)
        delta = (row.next_run_at - now).total_seconds()
        return max(0.0, min(float(settings.scheduler_max_sleep_seconds), delta))
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

        if row.attempt_count >= max(1, row.max_attempts):
            row.status = "failed"
            row.backoff_until = None
        else:
            backoff_seconds = max(1, settings.job_retry_base_seconds) * (2 ** max(0, row.attempt_count - 1))
            row.status = "queued"
            row.backoff_until = now + timedelta(seconds=backoff_seconds)
            row.next_run_at = row.backoff_until
        db.commit()
    finally:
        db.close()


def _run_ingest_job() -> int:
    provider = get_provider()
    result = run_ingest_cycle(provider=provider)
    next_poll = int(result.get("next_poll_seconds", settings.ingest_pregame_cold_interval_seconds))
    return max(1, next_poll)


def _run_delivery_job() -> int:
    db = SessionLocal()
    try:
        sent_count, failed_count = process_pending_alerts(db, ingest_run_id=None)
        db.commit()
        has_activity = (sent_count + failed_count) > 0
        if has_activity:
            return max(1, settings.delivery_active_backoff_seconds)

        # If queue is empty, sleep longer; if queue has pending, keep short cadence.
        pending_count = count_pending_alerts(db)
        if pending_count > 0:
            return max(1, settings.delivery_active_backoff_seconds)
        return max(1, settings.delivery_empty_backoff_seconds)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_cleanup_job() -> int:
    db = SessionLocal()
    try:
        removed = cleanup_games_outside_window(db)
        db.commit()
        if removed:
            logger.info("Cleanup removed games=%s", removed)
        return max(60, settings.cleanup_interval_seconds)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run(stop_event: threading.Event) -> None:
    _bootstrap_jobs()
    logger.info("Scheduler loop started max_sleep=%ss", settings.scheduler_max_sleep_seconds)

    while not stop_event.is_set():
        now = _utcnow()
        due_job = _next_due_job(now)
        if due_job is None:
            stop_event.wait(_next_due_seconds(now))
            continue

        _mark_job_running(due_job.id, now)
        try:
            if due_job.job_type == INGEST_JOB:
                next_run = _run_ingest_job()
            elif due_job.job_type == DELIVERY_JOB:
                next_run = _run_delivery_job()
            elif due_job.job_type == CLEANUP_JOB:
                next_run = _run_cleanup_job()
            else:
                raise RuntimeError(f"unsupported job type: {due_job.job_type}")
            _mark_job_success(due_job.id, next_run, _utcnow())
        except Exception as exc:  # pragma: no cover - exercised through integration behavior
            logger.exception("Worker job failed job_type=%s", due_job.job_type)
            _mark_job_failed(due_job.id, str(exc), _utcnow())

    logger.info("Scheduler loop stopped")
