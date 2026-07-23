from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.league import LeagueSettingOut
from app.services.leagues import get_active_leagues, get_league_profile, list_league_settings

router = APIRouter(tags=["leagues"])


@router.get("/leagues", response_model=list[LeagueSettingOut])
def list_active_leagues(db: Session = Depends(get_db)) -> list[LeagueSettingOut]:
    active = set(get_active_leagues(db))
    items: list[LeagueSettingOut] = []
    for row in list_league_settings(db):
        if row.league not in active:
            continue
        profile = get_league_profile(row.league)
        items.append(
            LeagueSettingOut(
                league=row.league,
                sport=profile.sport,
                label=profile.label,
                badge_label=profile.badge_label,
                alert_types=list(profile.alert_types),
                live_sync_interval_seconds=profile.live_sync_interval_seconds,
                is_enabled=row.is_enabled,
            )
        )
    return items
