from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
    states: list[IngestHealthOut]
    events: list[IngestHealthEventOut]


class OpsAdminRiskThresholdsOut(BaseModel):
    utilization_watch_pct: float
    utilization_risk_pct: float
    error_watch_pct: float
    error_risk_pct: float


class OpsAdminGlobalHealthOut(BaseModel):
    status: str
    providers_at_risk: int
    providers_on_watch: int


class OpsAdminRiskCardOut(BaseModel):
    key: str
    label: str
    value: int
    status: str


class OpsAdminProviderOut(BaseModel):
    provider: str
    quota_limit_24h: int | None
    quota_limit_window: int | None
    total_calls: int
    success_calls: int
    error_calls: int
    rate_limited_calls: int
    utilization_pct: float | None
    remaining_budget: int | None
    calls_per_hour: float
    error_pct: float
    trend_delta_calls: int
    trend_direction: str
    status: str
    reasons: list[str]


class OpsAdminIncidentOut(BaseModel):
    id: str
    occurred_at: datetime
    provider: str | None
    type: str
    severity: str
    title: str
    detail: str


class OpsAdminMetaOut(BaseModel):
    last_updated_at: datetime
    window: str


class OpsAdminOverviewOut(BaseModel):
    global_health: OpsAdminGlobalHealthOut
    thresholds: OpsAdminRiskThresholdsOut
    risk_cards: list[OpsAdminRiskCardOut]
    providers: list[OpsAdminProviderOut]
    incidents: list[OpsAdminIncidentOut]
    meta: OpsAdminMetaOut


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
