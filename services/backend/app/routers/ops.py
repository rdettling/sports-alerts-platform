from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Alert, AlertDelivery, CompetitionSetting, OddsApiDailyUsage, User
from app.db.session import get_db
from app.deps import require_admin_user
from app.schemas.competition import CompetitionSettingOut, UpdateCompetitionSettingRequest
from app.schemas.ops import (
    OpsAdminDeliveryOut,
    OpsAdminDeliveryStatsOut,
    OpsAdminSummaryOut,
    OpsAdminSummaryOverviewOut,
    OddsApiUsageOut,
)
from app.worker.odds_sync import ODDS_DAILY_CREDIT_CAP
from app.services import worker_schedule
from app.services.competitions import get_alert_types, get_competition_profile, list_competition_settings, normalize_competition
from app.services.game_feed import game_feed_cache

router = APIRouter(prefix="/ops", tags=["ops"])

WINDOW_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7}


def _window_start(window: str) -> datetime:
    if window not in WINDOW_TO_HOURS:
        raise HTTPException(status_code=422, detail="Invalid window")
    return datetime.now(timezone.utc) - timedelta(hours=WINDOW_TO_HOURS[window])


def _competition_setting_out(row: CompetitionSetting) -> CompetitionSettingOut:
    profile = get_competition_profile(row.competition)
    return CompetitionSettingOut(
        competition=row.competition,
        sport=profile.sport,
        label=profile.label,
        badge_label=profile.badge_label,
        alert_types=list(get_alert_types(row.competition)),
        live_sync_interval_seconds=profile.live_sync_interval_seconds,
        is_enabled=row.is_enabled,
    )


def _resolve_neon_dashboard_url() -> str | None:
    if settings.neon_dashboard_url.strip():
        return settings.neon_dashboard_url.strip()
    if settings.neon_project_id.strip():
        return f"https://console.neon.tech/app/projects/{settings.neon_project_id.strip()}"
    return None


@router.put("/competitions/{competition}", response_model=CompetitionSettingOut)
def update_competition_setting(
    competition: str,
    payload: UpdateCompetitionSettingRequest,
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CompetitionSettingOut:
    normalized = normalize_competition(competition)
    row = next((item for item in list_competition_settings(db) if item.competition == normalized), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Competition not found")
    row.is_enabled = payload.is_enabled
    db.commit()
    game_feed_cache.invalidate()
    db.refresh(row)
    return _competition_setting_out(row)


@router.get("/admin/summary", response_model=OpsAdminSummaryOut)
def admin_summary(
    window: str = Query(default="24h"),
    _: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> OpsAdminSummaryOut:
    start = _window_start(window)
    now = datetime.now(timezone.utc)
    delivery_counts: dict[str, dict[str, int]] = {"email": {}, "push": {}}
    for channel, status, count in db.execute(
        select(AlertDelivery.channel, AlertDelivery.status, func.count(AlertDelivery.id))
        .where(
            AlertDelivery.attempted_at >= start,
            AlertDelivery.channel.in_(("email", "push")),
        )
        .group_by(AlertDelivery.channel, AlertDelivery.status)
    ).all():
        delivery_counts[channel][status] = count

    email_counts = delivery_counts["email"]
    push_counts = delivery_counts["push"]
    alerts_created = db.scalar(select(func.count(Alert.id)).where(Alert.triggered_at >= start)) or 0
    usage = db.get(OddsApiDailyUsage, now.date())

    return OpsAdminSummaryOut(
        overview=OpsAdminSummaryOverviewOut(
            window=window,
            total_alerts_created=alerts_created,
            last_updated_at=now,
        ),
        delivery=OpsAdminDeliveryOut(
            email_alerts=OpsAdminDeliveryStatsOut(
                attempted=sum(email_counts.values()),
                sent=email_counts.get("sent", 0),
                failed=email_counts.get("failed", 0),
            ),
            push_alerts=OpsAdminDeliveryStatsOut(
                attempted=sum(push_counts.values()),
                sent=push_counts.get("sent", 0),
                failed=push_counts.get("failed", 0),
            ),
        ),
        schedule=worker_schedule.snapshot,
        odds_api_usage=OddsApiUsageOut(
            credits_used=usage.credits_used if usage else 0,
            daily_credit_cap=ODDS_DAILY_CREDIT_CAP,
            provider_credits_used=usage.provider_credits_used if usage else None,
            provider_credits_remaining=usage.provider_credits_remaining if usage else None,
            provider_observed_at=usage.provider_observed_at if usage else None,
        ),
        neon_dashboard_url=_resolve_neon_dashboard_url(),
        competition_settings=[_competition_setting_out(row) for row in list_competition_settings(db)],
    )
