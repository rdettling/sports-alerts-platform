from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiCallEvent, ApiCallRollupHourly


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    telemetry_raw_events_enabled: bool = False


telemetry_settings = TelemetrySettings()
_INGEST_PROVIDER_CALL_COUNTS: dict[tuple[int, str], int] = {}
_INGEST_PROVIDER_CALL_COUNTS_LOCK = Lock()


def consume_ingest_provider_call_counts(ingest_run_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    with _INGEST_PROVIDER_CALL_COUNTS_LOCK:
        matching = [key for key in _INGEST_PROVIDER_CALL_COUNTS if key[0] == ingest_run_id]
        for key in matching:
            _run_id, provider = key
            counts[provider] = _INGEST_PROVIDER_CALL_COUNTS.pop(key, 0)
    return counts


def _find_pending_rollup(
    db: Session,
    *,
    bucket_start: datetime,
    service: str,
    provider: str,
    endpoint_key: str,
    attempt_status: str,
) -> ApiCallRollupHourly | None:
    for obj in db.new:
        if not isinstance(obj, ApiCallRollupHourly):
            continue
        if (
            obj.bucket_start == bucket_start
            and obj.service == service
            and obj.provider == provider
            and obj.endpoint_key == endpoint_key
            and obj.attempt_status == attempt_status
        ):
            return obj
    return None


def record_api_call_event(
    db: Session,
    *,
    service: str,
    provider: str,
    endpoint_key: str,
    attempt_status: str,
    http_status: int | None = None,
    latency_ms: int | None = None,
    error_code: str | None = None,
    ingest_run_id: int | None = None,
    occurred_at: datetime | None = None,
) -> None:
    event_time = occurred_at or datetime.now(timezone.utc)
    bucket_start = event_time.replace(minute=0, second=0, microsecond=0)
    if ingest_run_id is not None:
        with _INGEST_PROVIDER_CALL_COUNTS_LOCK:
            key = (ingest_run_id, provider)
            _INGEST_PROVIDER_CALL_COUNTS[key] = _INGEST_PROVIDER_CALL_COUNTS.get(key, 0) + 1
    if telemetry_settings.telemetry_raw_events_enabled:
        event = ApiCallEvent(
            service=service,
            provider=provider,
            endpoint_key=endpoint_key,
            attempt_status=attempt_status,
            http_status=http_status,
            latency_ms=latency_ms,
            error_code=error_code,
            ingest_run_id=ingest_run_id,
            occurred_at=event_time,
        )
        db.add(event)

    pending_rollup = _find_pending_rollup(
        db,
        bucket_start=bucket_start,
        service=service,
        provider=provider,
        endpoint_key=endpoint_key,
        attempt_status=attempt_status,
    )
    if pending_rollup:
        pending_rollup.call_count += 1
        return

    rollup = db.scalar(
        select(ApiCallRollupHourly).where(
            ApiCallRollupHourly.bucket_start == bucket_start,
            ApiCallRollupHourly.service == service,
            ApiCallRollupHourly.provider == provider,
            ApiCallRollupHourly.endpoint_key == endpoint_key,
            ApiCallRollupHourly.attempt_status == attempt_status,
        )
    )
    if rollup:
        rollup.call_count += 1
        return

    db.add(
        ApiCallRollupHourly(
            bucket_start=bucket_start,
            service=service,
            provider=provider,
            endpoint_key=endpoint_key,
            attempt_status=attempt_status,
            call_count=1,
        )
    )
