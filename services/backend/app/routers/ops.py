from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Alert, AlertDelivery, ApiCallRollupHourly, LeagueSetting, User, WorkerJob
from app.db.session import get_db
from app.deps import require_admin_user
from app.schemas.league import LeagueSettingOut, UpdateLeagueSettingRequest
from app.schemas.ops import (
    OpsAdminDeliveryOut,
    OpsAdminDeliveryStatsOut,
    OpsAdminProviderOut,
    OpsAdminResendStatsOut,
    OpsAdminRuntimeJobOut,
    OpsAdminRuntimeOut,
    OpsAdminSummaryOut,
    OpsAdminSummaryOverviewOut,
    NeonUsageOut,
)
from app.services.leagues import (
    get_active_leagues,
    get_alert_types,
    get_league_profile,
    list_league_settings,
    normalize_league,
)

router = APIRouter(prefix="/ops", tags=["ops"])

WINDOW_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7}
ADMIN_OVERVIEW_WINDOWS = {"1h", "6h", "24h", "7d"}
NEON_API_BASE_URL = "https://console.neon.tech/api/v2"
OPS_PROVIDER_QUOTAS = {"espn": 5000, "odds": 1000}
ADMIN_PROVIDER_ORDER = ("espn", "odds", "resend")


def _window_start(window: str) -> datetime:
    if window not in WINDOW_TO_HOURS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=WINDOW_TO_HOURS[window])


def _canonical_provider_name(name: str) -> str:
    normalized = name.strip().lower()
    if normalized in {"the_odds_api", "oddsapi", "odds"}:
        return "odds"
    return normalized


def _league_setting_out(row: LeagueSetting) -> LeagueSettingOut:
    profile = get_league_profile(row.league)
    return LeagueSettingOut(
        league=row.league,
        sport=profile.sport,
        label=profile.label,
        badge_label=profile.badge_label,
        alert_types=list(get_alert_types(row.league)),
        live_sync_interval_seconds=profile.live_sync_interval_seconds,
        default_test_matchup=profile.default_test_matchup,
        is_enabled=row.is_enabled,
    )


def _resolve_neon_dashboard_url(project_id: str) -> str:
    if settings.neon_dashboard_url.strip():
        return settings.neon_dashboard_url.strip()
    return f"https://console.neon.tech/app/projects/{project_id}"


def _build_runtime(db: Session) -> OpsAdminRuntimeOut:
    active_leagues = get_active_leagues(db)
    jobs = db.scalars(select(WorkerJob).order_by(WorkerJob.job_type.asc(), WorkerJob.league.asc())).all()
    sync_jobs = [
        job
        for job in jobs
        if job.job_type in {"catalog_sync", "live_sync"} and (job.league is None or job.league in active_leagues)
    ]
    next_run_candidates = [job.next_run_at for job in sync_jobs if job.next_run_at is not None]
    next_run_at = min(next_run_candidates) if next_run_candidates else None
    last_success_at = max((job.last_finished_at for job in jobs if job.last_finished_at is not None), default=None)

    scheduler_mode = "off"
    if any(job.job_type == "live_sync" and job.status in {"queued", "running"} for job in sync_jobs):
        scheduler_mode = "live"

    return OpsAdminRuntimeOut(
        scheduler_mode=scheduler_mode,
        next_run_at=next_run_at,
        last_success_at=last_success_at,
        active_leagues=active_leagues,
        league_settings=[_league_setting_out(row) for row in list_league_settings(db)],
        jobs=[
            OpsAdminRuntimeJobOut(
                job_type=job.job_type,
                league=job.league,
                status=job.status,
                next_run_at=job.next_run_at,
                last_success_at=job.last_finished_at,
                backoff_until=job.backoff_until,
                last_error=job.last_error,
            )
            for job in jobs
        ],
    )


@router.put("/leagues/{league}", response_model=LeagueSettingOut)
def update_league_setting(
    league: str,
    payload: UpdateLeagueSettingRequest,
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> LeagueSettingOut:
    normalized = normalize_league(league)
    row = next((item for item in list_league_settings(db) if item.league == normalized), None)
    if row is None:
        raise HTTPException(status_code=404, detail="League not found")
    row.is_enabled = payload.is_enabled
    db.commit()
    db.refresh(row)
    return _league_setting_out(row)


@router.get("/admin/summary", response_model=OpsAdminSummaryOut)
def admin_summary(
    window: str = Query(default="24h"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> OpsAdminSummaryOut:
    if window not in ADMIN_OVERVIEW_WINDOWS:
        raise HTTPException(status_code=422, detail="Invalid window")

    start = _window_start(window)
    now = datetime.now(timezone.utc)
    hours = max(WINDOW_TO_HOURS[window], 1)

    rollups = db.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.bucket_start >= start)).all()
    by_provider: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_provider_endpoint: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in rollups:
        p = _canonical_provider_name(row.provider)
        metrics = by_provider[p]
        metrics["total_calls"] += row.call_count
        by_provider_endpoint[p][row.endpoint_key] += row.call_count
        if row.attempt_status == "success":
            metrics["success_calls"] += row.call_count
        elif row.attempt_status == "rate_limited":
            metrics["rate_limited_calls"] += row.call_count
        else:
            metrics["error_calls"] += row.call_count

    providers_out: list[OpsAdminProviderOut] = []
    resend_metrics = by_provider["resend"]

    for name in ADMIN_PROVIDER_ORDER:
        metrics = by_provider[name]
        total_calls = metrics.get("total_calls", 0)
        quota_limit_24h = OPS_PROVIDER_QUOTAS.get(name)
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
        endpoint_counts = by_provider_endpoint[name]
        most_used_endpoint = None
        if endpoint_counts:
            most_used_endpoint = max(endpoint_counts.items(), key=lambda item: (item[1], item[0]))[0]

        providers_out.append(
            OpsAdminProviderOut(
                provider=name,
                total_calls=total_calls,
                success_calls=metrics.get("success_calls", 0),
                error_calls=metrics.get("error_calls", 0),
                rate_limited_calls=metrics.get("rate_limited_calls", 0),
                calls_per_hour=round(total_calls / hours, 2),
                quota_limit_window=quota_limit_window,
                utilization_pct=utilization_pct,
                most_used_endpoint=most_used_endpoint,
            )
        )

    email_delivery_rows = db.scalars(
        select(AlertDelivery).where(
            AlertDelivery.attempted_at >= start,
            AlertDelivery.channel == "email",
        )
    ).all()
    push_delivery_rows = db.scalars(
        select(AlertDelivery).where(
            AlertDelivery.attempted_at >= start,
            AlertDelivery.channel == "push",
        )
    ).all()
    email_alert_attempted = len(email_delivery_rows)
    email_alert_sent = sum(1 for row in email_delivery_rows if row.status == "sent")
    email_alert_failed = sum(1 for row in email_delivery_rows if row.status == "failed")
    push_alert_attempted = len(push_delivery_rows)
    push_alert_sent = sum(1 for row in push_delivery_rows if row.status == "sent")
    push_alert_failed = sum(1 for row in push_delivery_rows if row.status == "failed")
    alerts_created = db.scalar(select(func.count(Alert.id)).where(Alert.triggered_at >= start)) or 0

    magic_attempted = max(resend_metrics.get("total_calls", 0) - email_alert_attempted, 0)
    magic_sent = max(resend_metrics.get("success_calls", 0) - email_alert_sent, 0)
    magic_failed = max(magic_attempted - magic_sent, 0)

    return OpsAdminSummaryOut(
        overview=OpsAdminSummaryOverviewOut(
            window=window,
            total_provider_calls=sum(row.total_calls for row in providers_out),
            provider_errors=sum(row.error_calls for row in providers_out),
            provider_rate_limits=sum(row.rate_limited_calls for row in providers_out),
            total_emails_attempted=email_alert_attempted + magic_attempted,
            emails_sent=email_alert_sent + magic_sent,
            emails_failed=email_alert_failed + magic_failed,
            total_alerts_created=alerts_created,
            last_updated_at=now,
        ),
        providers=providers_out,
        delivery=OpsAdminDeliveryOut(
            email_alerts=OpsAdminDeliveryStatsOut(
                attempted=email_alert_attempted,
                sent=email_alert_sent,
                failed=email_alert_failed,
            ),
            push_alerts=OpsAdminDeliveryStatsOut(
                attempted=push_alert_attempted,
                sent=push_alert_sent,
                failed=push_alert_failed,
            ),
            magic_links=OpsAdminDeliveryStatsOut(attempted=magic_attempted, sent=magic_sent, failed=magic_failed),
            resend=OpsAdminResendStatsOut(
                total_calls=resend_metrics.get("total_calls", 0),
                success_calls=resend_metrics.get("success_calls", 0),
                error_calls=resend_metrics.get("error_calls", 0),
                rate_limited_calls=resend_metrics.get("rate_limited_calls", 0),
            ),
        ),
        runtime=_build_runtime(db),
    )


@router.get("/db/neon-usage", response_model=NeonUsageOut)
def neon_usage(_: User = Depends(require_admin_user)) -> NeonUsageOut:
    if not settings.neon_api_key.strip():
        return NeonUsageOut(available=False, message="NEON_API_KEY is not configured.")
    if not settings.neon_project_id.strip():
        return NeonUsageOut(available=False, message="NEON_PROJECT_ID is not configured.")

    headers = {"Authorization": f"Bearer {settings.neon_api_key.strip()}"}
    project_id = settings.neon_project_id.strip()
    org_id = settings.neon_org_id.strip()
    params = {"org_id": org_id} if org_id else None

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{NEON_API_BASE_URL}/projects/{project_id}", headers=headers, params=params)
            response.raise_for_status()
            raw = response.json()
    except Exception as exc:
        return NeonUsageOut(available=False, message=f"Failed to load Neon stats: {exc}")

    data = raw.get("project", raw) if isinstance(raw, dict) else {}

    cpu_used_sec = data.get("cpu_used_sec")
    active_time_sec = data.get("active_time_seconds")
    avg_cu_while_active: float | None = None
    if isinstance(cpu_used_sec, int) and isinstance(active_time_sec, int) and active_time_sec > 0:
        avg_cu_while_active = round(cpu_used_sec / active_time_sec, 3)

    return NeonUsageOut(
        available=True,
        project_id=data.get("id"),
        project_name=data.get("name"),
        dashboard_url=_resolve_neon_dashboard_url(project_id),
        consumption_period_start=data.get("consumption_period_start"),
        consumption_period_end=data.get("consumption_period_end"),
        cpu_used_sec=cpu_used_sec,
        active_time_sec=active_time_sec,
        compute_last_active_at=data.get("compute_last_active_at"),
        avg_cu_while_active=avg_cu_while_active,
    )
