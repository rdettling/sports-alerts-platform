from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.competition import CompetitionSettingOut


class OpsAdminSummaryOverviewOut(BaseModel):
    window: str
    total_alerts_created: int
    last_updated_at: datetime


class OpsAdminDeliveryStatsOut(BaseModel):
    attempted: int
    sent: int
    failed: int


class OpsAdminDeliveryOut(BaseModel):
    email_alerts: OpsAdminDeliveryStatsOut
    push_alerts: OpsAdminDeliveryStatsOut


class OpsAdminSummaryOut(BaseModel):
    overview: OpsAdminSummaryOverviewOut
    delivery: OpsAdminDeliveryOut
    competition_settings: list[CompetitionSettingOut]


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
