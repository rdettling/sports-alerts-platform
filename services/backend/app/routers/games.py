from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.game import GameOut
from app.services.game_feed import game_feed_cache, load_games

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameOut])
def list_games(
    response: Response,
    status: str | None = Query(default=None, description="Filter by game status"),
    competition: str | None = Query(default=None, description="Filter by competition, e.g. NBA or MLB"),
    include_finals: bool = Query(default=False, description="Include final games in results"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[GameOut]:
    response.headers["Cache-Control"] = "no-store"
    if status is None and competition is None and include_finals and limit == 500:
        return game_feed_cache.get()
    return load_games(
        db, status=status, competition=competition, include_finals=include_finals, limit=limit,
    )
