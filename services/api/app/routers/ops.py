from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Alert, AlertDelivery, ApiCallRollupHourly, LeagueSetting, Team, User, WorkerJob
from app.db.session import get_db
from app.deps import require_admin_user
from app.schemas.league import LeagueSettingOut, UpdateLeagueSettingRequest
from app.schemas.ops import (
    ApiUsageSummaryOut,
    IngestHealthEventOut,
    IngestHealthOut,
    IngestHealthResponseOut,
    ApiUsageTimeseriesOut,
    ApiUsageTimeseriesPointOut,
    EndpointUsageOut,
    ExpectedActualOut,
    OpsAdminDeliveryOut,
    OpsAdminDeliveryStatsOut,
    OpsAdminProviderOut,
    OpsAdminResendStatsOut,
    OpsAdminRuntimeJobOut,
    OpsAdminRuntimeOut,
    OpsAdminSummaryOut,
    OpsAdminSummaryOverviewOut,
    NeonUsageOut,
    ProviderUsageOut,
    TeamMappingHealthOut,
    TeamMappingLeagueHealthOut,
    OpsLeagueSettingsResponseOut,
)
from app.services.leagues import (
    get_active_leagues,
    get_alert_types,
    get_league_profile,
    get_scoreboard_url,
    list_league_settings,
    normalize_league,
)

router = APIRouter(prefix="/ops", tags=["ops"])

WINDOW_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7, "30d": 24 * 30}
TIMESERIES_WINDOWS = {"24h": 24, "7d": 24 * 7}
ADMIN_OVERVIEW_WINDOWS = {"1h", "6h", "24h", "7d"}
NEON_API_BASE_URL = "https://console.neon.tech/api/v2"
OPS_PROVIDER_QUOTAS = {"espn": 5000, "odds": 1000}
ADMIN_PROVIDER_ORDER = ("espn", "odds", "resend")


def _window_start(window: str) -> datetime:
    if window not in WINDOW_TO_HOURS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=WINDOW_TO_HOURS[window])


def _timeseries_window_start(window: str) -> datetime:
    if window not in TIMESERIES_WINDOWS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=TIMESERIES_WINDOWS[window])


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

    provider_expected = {"espn": None, "odds": None}
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
            "espn": ExpectedActualOut(expected=0, actual=0),
            "odds": ExpectedActualOut(expected=0, actual=0),
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
                expected_calls=None,
            )
        )
    return ApiUsageTimeseriesOut(window=window, bucket=bucket, points=points)


@router.get("/db/ingest-health", response_model=IngestHealthResponseOut)
def ingest_health(
    event_limit: int = Query(default=20, ge=1, le=200),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> IngestHealthResponseOut:
    runtime = _build_runtime(db)
    jobs = db.scalars(select(WorkerJob).order_by(WorkerJob.job_type.asc(), WorkerJob.league.asc())).all()
    return IngestHealthResponseOut(
        scheduler_mode=runtime.scheduler_mode,
        next_run_at=runtime.next_run_at,
        last_success_at=runtime.last_success_at,
        active_leagues=runtime.active_leagues,
        states=[
            IngestHealthOut(
                source_key=f"worker:{job.job_type}:{job.league or 'global'}",
                mode=job.status,
                next_due_at=job.next_run_at,
                last_success_at=job.last_finished_at,
                backoff_until=job.backoff_until,
                last_error=job.last_error,
            )
            for job in jobs
        ],
        events=[],
    )


@router.get("/leagues", response_model=OpsLeagueSettingsResponseOut)
def get_league_settings(
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> OpsLeagueSettingsResponseOut:
    return OpsLeagueSettingsResponseOut(
        items=[_league_setting_out(row) for row in list_league_settings(db)]
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


@router.get("/db/team-mapping-health", response_model=TeamMappingHealthOut)
def team_mapping_health(
    date: str | None = Query(default=None, description="Date in YYYYMMDD format"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> TeamMappingHealthOut:
    check_date = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    if len(check_date) != 8 or not check_date.isdigit():
        raise HTTPException(status_code=422, detail="Invalid date. Use YYYYMMDD.")

    leagues_out: list[TeamMappingLeagueHealthOut] = []
    for league in get_active_leagues(db):
        seeded_team_ids = {
            team_id
            for team_id, in db.execute(select(Team.external_team_id).where(Team.league == league)).all()
        }
        missing_team_ids: set[str] = set()
        checked_games = 0
        checked_team_refs = 0
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(get_scoreboard_url(league), params={"dates": check_date})
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to load {league} scoreboard for {check_date}: {exc}") from exc

        for event in payload.get("events", []):
            checked_games += 1
            competition = (event.get("competitions") or [{}])[0]
            for competitor in competition.get("competitors", []):
                team = competitor.get("team") or {}
                team_id = str(team.get("id") or "").strip()
                if not team_id:
                    continue
                checked_team_refs += 1
                if team_id not in seeded_team_ids:
                    missing_team_ids.add(team_id)
        leagues_out.append(
            TeamMappingLeagueHealthOut(
                league=league,
                checked_games=checked_games,
                checked_team_refs=checked_team_refs,
                missing_team_ids=sorted(missing_team_ids, key=lambda value: int(value) if value.isdigit() else value),
            )
        )

    return TeamMappingHealthOut(
        ok=all(not league.missing_team_ids for league in leagues_out),
        checked_at=datetime.now(timezone.utc),
        leagues=leagues_out,
    )
