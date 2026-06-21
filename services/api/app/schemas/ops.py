from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from app.schemas.league import LeagueSettingOut


class ProviderUsageOut(BaseModel):
    provider: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    expected_calls: int | None = None


class EndpointUsageOut(BaseModel):
    provider: str
    endpoint_key: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int


class ExpectedActualOut(BaseModel):
    expected: int
    actual: int


class ApiUsageSummaryOut(BaseModel):
    window: str
    totals: dict[str, int]
    expected_vs_actual: dict[str, ExpectedActualOut]
    by_provider: list[ProviderUsageOut]
    by_endpoint: list[EndpointUsageOut]


class ApiUsageTimeseriesPointOut(BaseModel):
    bucket_start: datetime
    provider: str
    actual_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    expected_calls: int | None = None


class ApiUsageTimeseriesOut(BaseModel):
    window: str
    bucket: str
    points: list[ApiUsageTimeseriesPointOut]


class IngestHealthEventOut(BaseModel):
    id: int
    source_key: str
    event_type: str
    mode: str | None
    message: str | None
    occurred_at: datetime


class IngestHealthOut(BaseModel):
    source_key: str
    mode: str
    next_due_at: datetime | None
    last_success_at: datetime | None
    backoff_until: datetime | None
    last_error: str | None


class IngestHealthResponseOut(BaseModel):
    scheduler_mode: str
    next_run_at: datetime | None
    last_success_at: datetime | None
    active_leagues: list[str]
    states: list[IngestHealthOut]
    events: list[IngestHealthEventOut]


class OpsAdminSummaryOverviewOut(BaseModel):
    window: str
    total_provider_calls: int
    provider_errors: int
    provider_rate_limits: int
    total_emails_attempted: int
    emails_sent: int
    emails_failed: int
    total_alerts_created: int
    last_updated_at: datetime


class OpsAdminProviderOut(BaseModel):
    provider: str
    total_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    calls_per_hour: float
    quota_limit_window: int | None
    utilization_pct: float | None
    most_used_endpoint: str | None


class OpsAdminDeliveryStatsOut(BaseModel):
    attempted: int
    sent: int
    failed: int


class OpsAdminResendStatsOut(BaseModel):
    total_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int


class OpsAdminDeliveryOut(BaseModel):
    alerts: OpsAdminDeliveryStatsOut
    magic_links: OpsAdminDeliveryStatsOut
    resend: OpsAdminResendStatsOut


class OpsAdminRuntimeJobOut(BaseModel):
    job_type: str
    league: str | None
    status: str
    next_run_at: datetime | None
    last_success_at: datetime | None
    backoff_until: datetime | None
    last_error: str | None


class OpsAdminRuntimeOut(BaseModel):
    scheduler_mode: str
    next_run_at: datetime | None
    last_success_at: datetime | None
    active_leagues: list[str]
    league_settings: list[LeagueSettingOut]
    jobs: list[OpsAdminRuntimeJobOut]


class OpsAdminSummaryOut(BaseModel):
    overview: OpsAdminSummaryOverviewOut
    providers: list[OpsAdminProviderOut]
    delivery: OpsAdminDeliveryOut
    runtime: OpsAdminRuntimeOut


class NeonUsageOut(BaseModel):
    available: bool
    project_id: str | None = None
    project_name: str | None = None
    dashboard_url: str | None = None
    consumption_period_start: datetime | None = None
    consumption_period_end: datetime | None = None
    cpu_used_sec: int | None = None
    active_time_sec: int | None = None
    compute_last_active_at: datetime | None = None
    avg_cu_while_active: float | None = None
    message: str | None = None


class TeamMappingLeagueHealthOut(BaseModel):
    league: str
    checked_games: int
    checked_team_refs: int
    missing_team_ids: list[str]


class TeamMappingHealthOut(BaseModel):
    ok: bool
    checked_at: datetime
    leagues: list[TeamMappingLeagueHealthOut]


class OpsLeagueSettingsResponseOut(BaseModel):
    items: list[LeagueSettingOut]
