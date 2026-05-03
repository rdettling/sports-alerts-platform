from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
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
    OpsAdminGlobalHealthOut,
    OpsAdminMetaOut,
    OpsAdminOverviewOut,
    OpsAdminProviderOut,
    OpsAdminRiskCardOut,
    OpsAdminRiskThresholdsOut,
    ProviderUsageOut,
)

router = APIRouter(prefix="/ops", tags=["ops"])

WINDOW_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7, "30d": 24 * 30}
TIMESERIES_WINDOWS = {"24h": 24, "7d": 24 * 7}
ADMIN_OVERVIEW_WINDOWS = {"1h", "6h", "24h", "7d"}


def _window_start(window: str) -> datetime:
    if window not in WINDOW_TO_HOURS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=WINDOW_TO_HOURS[window])


def _timeseries_window_start(window: str) -> datetime:
    if window not in TIMESERIES_WINDOWS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=TIMESERIES_WINDOWS[window])


def _to_ingest_usage(row: IngestRun) -> IngestRunUsageOut:
    return IngestRunUsageOut(
        ingest_run_id=row.id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        cycle_duration_seconds=(
            int((row.completed_at - row.started_at).total_seconds())
            if row.completed_at is not None and row.started_at is not None
            else None
        ),
        status=row.status,
        poll_mode=row.poll_mode,
        games_checked=row.games_checked,
        games_updated=row.games_updated,
        expected_espn_calls=row.expected_espn_calls,
        actual_espn_calls=row.actual_espn_calls,
        expected_odds_calls=row.expected_odds_calls,
        actual_odds_calls=row.actual_odds_calls,
    )


def _risk_status(
    *,
    utilization_pct: float | None,
    error_pct: float,
    rate_limited_calls: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    status = "healthy"

    if utilization_pct is not None and utilization_pct >= settings.ops_risk_utilization_risk_pct:
        status = "at_risk"
        reasons.append(f"Utilization {utilization_pct:.1f}% ≥ {settings.ops_risk_utilization_risk_pct:.0f}%")
    elif utilization_pct is not None and utilization_pct >= settings.ops_risk_utilization_watch_pct:
        status = "watch"
        reasons.append(f"Utilization {utilization_pct:.1f}% ≥ {settings.ops_risk_utilization_watch_pct:.0f}%")

    if error_pct >= settings.ops_risk_error_risk_pct:
        status = "at_risk"
        reasons.append(f"Error rate {error_pct:.1f}% ≥ {settings.ops_risk_error_risk_pct:.0f}%")
    elif error_pct >= settings.ops_risk_error_watch_pct and status != "at_risk":
        status = "watch"
        reasons.append(f"Error rate {error_pct:.1f}% ≥ {settings.ops_risk_error_watch_pct:.0f}%")

    if rate_limited_calls > 0:
        status = "at_risk"
        reasons.append(f"{rate_limited_calls} rate-limited responses in window")

    if not reasons:
        reasons.append("Within configured thresholds")

    return status, reasons


def _canonical_provider_name(name: str) -> str:
    normalized = name.strip().lower()
    if normalized in {"the_odds_api", "oddsapi", "odds"}:
        return "odds"
    return normalized


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
    return IngestRunUsageListOut(items=[_to_ingest_usage(row) for row in rows])


@router.get("/admin/overview", response_model=OpsAdminOverviewOut)
def admin_overview(
    window: str = Query(default="24h"),
    provider: str | None = Query(default=None),
    _limit: int = Query(default=25, ge=1, le=250),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> OpsAdminOverviewOut:
    if window not in ADMIN_OVERVIEW_WINDOWS:
        raise HTTPException(status_code=422, detail="Invalid window")

    start = _window_start(window)
    now = datetime.now(timezone.utc)

    rollups = db.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.bucket_start >= start)).all()
    ingest_runs = db.scalars(select(IngestRun).where(IngestRun.started_at >= start).order_by(desc(IngestRun.started_at))).all()

    by_provider: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_provider_hour_bucket: dict[str, dict[datetime, int]] = defaultdict(lambda: defaultdict(int))

    for row in rollups:
        p = _canonical_provider_name(row.provider)
        metrics = by_provider[p]
        metrics["total_calls"] += row.call_count
        by_provider_hour_bucket[p][row.bucket_start] += row.call_count
        if row.attempt_status == "success":
            metrics["success_calls"] += row.call_count
        elif row.attempt_status == "rate_limited":
            metrics["rate_limited_calls"] += row.call_count
        else:
            metrics["error_calls"] += row.call_count

    provider_names = sorted(by_provider.keys())
    if provider:
        provider_names = [name for name in provider_names if name == provider]

    providers_out: list[OpsAdminProviderOut] = []

    for name in provider_names:
        metrics = by_provider[name]
        total_calls = metrics.get("total_calls", 0)
        error_calls = metrics.get("error_calls", 0)
        rate_limited_calls = metrics.get("rate_limited_calls", 0)
        success_calls = metrics.get("success_calls", 0)

        hours = max(WINDOW_TO_HOURS[window], 1)
        quota_limit_24h = settings.ops_provider_quotas.get(name)
        quota_limit_window = (
            int(round(quota_limit_24h * (hours / 24.0)))
            if quota_limit_24h is not None and quota_limit_24h > 0
            else None
        )
        utilization_pct = (
            round((total_calls / quota_limit_window) * 100, 2)
            if quota_limit_window is not None and quota_limit_window > 0
            else None
        )
        remaining_budget = (
            max(quota_limit_window - total_calls, 0)
            if quota_limit_window is not None and quota_limit_window > 0
            else None
        )
        calls_per_hour = round(total_calls / hours, 2)
        error_pct = round((error_calls / total_calls) * 100, 2) if total_calls > 0 else 0.0

        hourly_calls = by_provider_hour_bucket[name]
        buckets = sorted(hourly_calls.keys())
        latest_calls = hourly_calls[buckets[-1]] if buckets else 0
        previous_calls = hourly_calls[buckets[-2]] if len(buckets) > 1 else latest_calls
        trend_delta = latest_calls - previous_calls
        trend_direction = "up" if trend_delta > 0 else "down" if trend_delta < 0 else "flat"

        status, reasons = _risk_status(
            utilization_pct=utilization_pct,
            error_pct=error_pct,
            rate_limited_calls=rate_limited_calls,
        )

        providers_out.append(
            OpsAdminProviderOut(
                provider=name,
                quota_limit_24h=quota_limit_24h,
                quota_limit_window=quota_limit_window,
                total_calls=total_calls,
                success_calls=success_calls,
                error_calls=error_calls,
                rate_limited_calls=rate_limited_calls,
                utilization_pct=utilization_pct,
                remaining_budget=remaining_budget,
                calls_per_hour=calls_per_hour,
                error_pct=error_pct,
                trend_delta_calls=trend_delta,
                trend_direction=trend_direction,
                status=status,
                reasons=reasons,
            )
        )

    providers_out.sort(
        key=lambda row: (
            0 if row.status == "at_risk" else 1 if row.status == "watch" else 2,
            -(row.utilization_pct or 0),
            -row.rate_limited_calls,
            -row.error_pct,
        )
    )

    providers_at_risk = sum(1 for row in providers_out if row.status == "at_risk")
    providers_on_watch = sum(1 for row in providers_out if row.status == "watch")
    global_status = "at_risk" if providers_at_risk > 0 else "watch" if providers_on_watch > 0 else "healthy"

    risk_cards = [
        OpsAdminRiskCardOut(
            key="providers_at_risk",
            label="Providers at risk",
            value=providers_at_risk,
            status="high" if providers_at_risk > 0 else "ok",
        ),
        OpsAdminRiskCardOut(
            key="rate_limited_events",
            label="Rate-limited events",
            value=sum(row.rate_limited_calls for row in providers_out),
            status="high" if sum(row.rate_limited_calls for row in providers_out) > 0 else "ok",
        ),
        OpsAdminRiskCardOut(
            key="providers_on_watch",
            label="Providers on watch",
            value=providers_on_watch,
            status="medium" if providers_on_watch > 0 else "ok",
        ),
        OpsAdminRiskCardOut(
            key="recent_failures",
            label="Ingest failures",
            value=sum(1 for run in ingest_runs if run.status != "success"),
            status="high" if any(run.status != "success" for run in ingest_runs) else "ok",
        ),
    ]

    return OpsAdminOverviewOut(
        global_health=OpsAdminGlobalHealthOut(
            status=global_status,
            providers_at_risk=providers_at_risk,
            providers_on_watch=providers_on_watch,
        ),
        thresholds=OpsAdminRiskThresholdsOut(
            utilization_watch_pct=settings.ops_risk_utilization_watch_pct,
            utilization_risk_pct=settings.ops_risk_utilization_risk_pct,
            error_watch_pct=settings.ops_risk_error_watch_pct,
            error_risk_pct=settings.ops_risk_error_risk_pct,
        ),
        risk_cards=risk_cards,
        providers=providers_out,
        incidents=[],
        meta=OpsAdminMetaOut(last_updated_at=now, window=window),
    )
