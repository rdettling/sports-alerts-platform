from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game
from app.db.session import get_db
from app.schemas.game import GameOut

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameOut])
def list_games(
    status: str | None = Query(default=None, description="Filter by game status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[GameOut]:
    stmt = select(Game).order_by(Game.scheduled_start_time.asc()).limit(limit)
    if status:
        stmt = stmt.where(Game.status == status)
    else:
        now = datetime.now(timezone.utc)
        stmt = stmt.where((Game.scheduled_start_time >= now) | (Game.status.in_(["live", "in_progress"])))
    games = db.scalars(stmt).all()
    return [GameOut.model_validate(game) for game in games]
