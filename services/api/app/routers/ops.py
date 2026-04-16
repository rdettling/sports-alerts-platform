from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import ApiCallRollupHourly, IngestRun, User
from app.db.session import get_db
from app.deps import require_admin_user
from app.schemas.ops import (
    ApiUsageSummaryOut,
    ApiUsageTimeseriesOut,
    ApiUsageTimeseriesPointOut,
    EndpointUsageOut,
    ExpectedActualOut,
    IngestRunUsageListOut,
    IngestRunUsageOut,
    ProviderUsageOut,
)

router = APIRouter(prefix="/ops", tags=["ops"])

WINDOW_TO_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
TIMESERIES_WINDOWS = {"24h": 24, "7d": 24 * 7}


def _window_start(window: str) -> datetime:
    if window not in WINDOW_TO_HOURS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=WINDOW_TO_HOURS[window])


def _timeseries_window_start(window: str) -> datetime:
    if window not in TIMESERIES_WINDOWS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=TIMESERIES_WINDOWS[window])


@router.get("/api-usage/summary", response_model=ApiUsageSummaryOut)
def api_usage_summary(
    window: str = Query(default="24h"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiUsageSummaryOut:
    start = _window_start(window)
    rollups = db.scalars(
        select(ApiCallRollupHourly).where(
            ApiCallRollupHourly.bucket_start >= start,
        )
    ).all()
    ingest_runs = db.scalars(
        select(IngestRun).where(
            IngestRun.started_at >= start,
        )
    ).all()

    provider_accumulator: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    endpoint_accumulator: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals = {"actual_calls": 0, "success_calls": 0, "error_calls": 0, "rate_limited_calls": 0}

    for row in rollups:
        provider_metrics = provider_accumulator[row.provider]
        endpoint_metrics = endpoint_accumulator[(row.provider, row.endpoint_key)]
        provider_metrics["actual_calls"] += row.call_count
        endpoint_metrics["actual_calls"] += row.call_count
        totals["actual_calls"] += row.call_count
        if row.attempt_status == "success":
            provider_metrics["success_calls"] += row.call_count
            endpoint_metrics["success_calls"] += row.call_count
            totals["success_calls"] += row.call_count
        elif row.attempt_status == "rate_limited":
            provider_metrics["rate_limited_calls"] += row.call_count
            endpoint_metrics["rate_limited_calls"] += row.call_count
            totals["rate_limited_calls"] += row.call_count
        else:
            provider_metrics["error_calls"] += row.call_count
            endpoint_metrics["error_calls"] += row.call_count
            totals["error_calls"] += row.call_count

    expected_espn = sum(run.expected_espn_calls for run in ingest_runs)
    expected_odds = sum(run.expected_odds_calls for run in ingest_runs)
    actual_espn = sum(run.actual_espn_calls for run in ingest_runs)
    actual_odds = sum(run.actual_odds_calls for run in ingest_runs)

    provider_expected = {"espn": expected_espn, "odds": expected_odds}
    by_provider = [
        ProviderUsageOut(
            provider=provider,
            actual_calls=metrics.get("actual_calls", 0),
            success_calls=metrics.get("success_calls", 0),
            error_calls=metrics.get("error_calls", 0),
            rate_limited_calls=metrics.get("rate_limited_calls", 0),
            expected_calls=provider_expected.get(provider),
        )
        for provider, metrics in sorted(provider_accumulator.items())
    ]
    by_endpoint = [
        EndpointUsageOut(
            provider=provider,
            endpoint_key=endpoint_key,
            actual_calls=metrics.get("actual_calls", 0),
            success_calls=metrics.get("success_calls", 0),
            error_calls=metrics.get("error_calls", 0),
            rate_limited_calls=metrics.get("rate_limited_calls", 0),
        )
        for (provider, endpoint_key), metrics in sorted(endpoint_accumulator.items())
    ]

    return ApiUsageSummaryOut(
        window=window,
        totals=totals,
        expected_vs_actual={
            "espn": ExpectedActualOut(expected=expected_espn, actual=actual_espn),
            "odds": ExpectedActualOut(expected=expected_odds, actual=actual_odds),
        },
        by_provider=by_provider,
        by_endpoint=by_endpoint,
    )


@router.get("/api-usage/timeseries", response_model=ApiUsageTimeseriesOut)
def api_usage_timeseries(
    window: str = Query(default="24h"),
    bucket: str = Query(default="hour"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ApiUsageTimeseriesOut:
    if bucket != "hour":
        raise HTTPException(status_code=422, detail="Invalid bucket")
    start = _timeseries_window_start(window)

    rollups = db.scalars(
        select(ApiCallRollupHourly).where(
            ApiCallRollupHourly.bucket_start >= start,
        )
    ).all()
    ingest_runs = db.scalars(
        select(IngestRun).where(
            IngestRun.started_at >= start,
        )
    ).all()

    expected_by_bucket_provider: dict[tuple[datetime, str], int] = defaultdict(int)
    for run in ingest_runs:
        bucket_start = run.started_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        expected_by_bucket_provider[(bucket_start, "espn")] += run.expected_espn_calls
        expected_by_bucket_provider[(bucket_start, "odds")] += run.expected_odds_calls

    points_acc: dict[tuple[datetime, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rollups:
        key = (row.bucket_start, row.provider)
        point = points_acc[key]
        point["actual_calls"] += row.call_count
        if row.attempt_status == "success":
            point["success_calls"] += row.call_count
        elif row.attempt_status == "rate_limited":
            point["rate_limited_calls"] += row.call_count
        else:
            point["error_calls"] += row.call_count

    points = []
    for (bucket_start, provider), metrics in sorted(points_acc.items()):
        points.append(
            ApiUsageTimeseriesPointOut(
                bucket_start=bucket_start,
                provider=provider,
                actual_calls=metrics.get("actual_calls", 0),
                success_calls=metrics.get("success_calls", 0),
                error_calls=metrics.get("error_calls", 0),
                rate_limited_calls=metrics.get("rate_limited_calls", 0),
                expected_calls=expected_by_bucket_provider.get((bucket_start, provider)),
            )
        )
    return ApiUsageTimeseriesOut(window=window, bucket=bucket, points=points)


@router.get("/api-usage/ingest-runs", response_model=IngestRunUsageListOut)
def api_usage_ingest_runs(
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> IngestRunUsageListOut:
    rows = db.scalars(select(IngestRun).order_by(desc(IngestRun.started_at)).limit(limit)).all()
    return IngestRunUsageListOut(
        items=[
            IngestRunUsageOut(
                ingest_run_id=row.id,
                started_at=row.started_at,
                completed_at=row.completed_at,
                status=row.status,
                poll_mode=row.poll_mode,
                expected_espn_calls=row.expected_espn_calls,
                actual_espn_calls=row.actual_espn_calls,
                expected_odds_calls=row.expected_odds_calls,
                actual_odds_calls=row.actual_odds_calls,
            )
            for row in rows
        ]
    )
