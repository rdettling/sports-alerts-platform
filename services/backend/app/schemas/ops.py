from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.competition import CompetitionSettingOut
from app.schemas.schedule import ScheduleSnapshot


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


class OddsApiUsageOut(BaseModel):
    credits_used: int
    daily_credit_cap: int
    provider_credits_used: int | None = None
    provider_credits_remaining: int | None = None
    provider_observed_at: datetime | None = None


class OpsAdminSummaryOut(BaseModel):
    overview: OpsAdminSummaryOverviewOut
    delivery: OpsAdminDeliveryOut
    competition_settings: list[CompetitionSettingOut]
    schedule: ScheduleSnapshot | None = None
    odds_api_usage: OddsApiUsageOut
    neon_dashboard_url: str | None = None
