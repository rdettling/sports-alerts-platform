from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.competition import CompetitionSettingOut
from app.services.competitions import get_active_competitions, get_alert_types, get_competition_profile, list_competition_settings

router = APIRouter(tags=["competitions"])


@router.get("/competitions", response_model=list[CompetitionSettingOut])
def list_active_competitions(db: Session = Depends(get_db)) -> list[CompetitionSettingOut]:
    active = set(get_active_competitions(db))
    items: list[CompetitionSettingOut] = []
    for row in list_competition_settings(db):
        if row.competition not in active:
            continue
        profile = get_competition_profile(row.competition)
        items.append(
            CompetitionSettingOut(
                competition=row.competition,
                sport=profile.sport,
                label=profile.label,
                badge_label=profile.badge_label,
                alert_types=list(get_alert_types(row.competition)),
                live_sync_interval_seconds=profile.live_sync_interval_seconds,
                is_enabled=row.is_enabled,
            )
        )
    return items
