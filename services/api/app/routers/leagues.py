from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.league import LeagueSettingOut
from app.services.leagues import get_active_leagues, list_league_settings

router = APIRouter(tags=["leagues"])


@router.get("/leagues", response_model=list[LeagueSettingOut])
def list_active_leagues(db: Session = Depends(get_db)) -> list[LeagueSettingOut]:
    active = set(get_active_leagues(db))
    return [LeagueSettingOut(league=row.league, is_enabled=row.is_enabled) for row in list_league_settings(db) if row.league in active]
