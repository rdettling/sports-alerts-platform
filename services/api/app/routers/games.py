from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Game, GameOddsCurrent
from app.db.session import get_db
from app.schemas.game import GameOddsOut, GameOut

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameOut])
def list_games(
    status: str | None = Query(default=None, description="Filter by game status"),
    include_odds: bool = Query(default=True, description="Include moneyline odds when configured"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[GameOut]:
    stmt = select(Game).order_by(Game.scheduled_start_time.asc()).limit(limit)
    if status:
        stmt = stmt.where(Game.status == status)
    else:
        stmt = stmt.where(Game.is_final.is_(False))
    games = db.scalars(stmt).all()
    game_views = [GameOut.model_validate(game) for game in games]
    if not include_odds or not games:
        return game_views

    game_ids = [game.id for game in games]
    odds_rows = db.scalars(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id.in_(game_ids),
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == settings.odds_api_market,
        )
    ).all()
    odds_by_game_id = {row.game_id: row for row in odds_rows}

    for game_view in game_views:
        odds = odds_by_game_id.get(game_view.id)
        if not odds:
            continue
        game_view.odds = GameOddsOut(
            home_moneyline=odds.home_moneyline,
            away_moneyline=odds.away_moneyline,
            bookmaker=odds.bookmaker,
            last_update=odds.fetched_at,
        )

    return game_views
