from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db.models import Game, GameOddsCurrent
from app.db.session import get_db
from app.schemas.game import GameOddsOut, GameOddsOutcomeOut, GameOut
from app.services.leagues import get_active_leagues, normalize_league

router = APIRouter(tags=["games"])
GAMES_RETENTION_PAST_HOURS = 36
GAMES_RETENTION_FUTURE_DAYS = 7


@router.get("/games", response_model=list[GameOut])
def list_games(
    status: str | None = Query(default=None, description="Filter by game status"),
    league: str | None = Query(default=None, description="Filter by league, e.g. NBA or MLB"),
    include_finals: bool = Query(default=False, description="Include final games in results"),
    include_odds: bool = Query(default=True, description="Include moneyline odds when configured"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[GameOut]:
    active_leagues = get_active_leagues(db)
    now = datetime.now(timezone.utc)
    lower = now - timedelta(hours=max(1, GAMES_RETENTION_PAST_HOURS))
    upper = now + timedelta(days=max(1, GAMES_RETENTION_FUTURE_DAYS))
    stmt = (
        select(Game)
        .where(Game.league.in_(active_leagues))
        .where(Game.scheduled_start_time >= lower, Game.scheduled_start_time <= upper)
        .order_by(Game.scheduled_start_time.asc())
        .limit(limit)
    )
    if league:
        stmt = stmt.where(Game.league == normalize_league(league))
    if status:
        stmt = stmt.where(Game.status == status)
    elif not include_finals:
        stmt = stmt.where(Game.is_final.is_(False))
    games = db.scalars(stmt).all()
    game_views = [GameOut.model_validate(game) for game in games]
    if not include_odds or not games:
        return game_views

    game_ids = [game.id for game in games]
    odds_rows = db.scalars(
        select(GameOddsCurrent)
        .options(selectinload(GameOddsCurrent.outcomes))
        .where(
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
            market=odds.market,
            bookmaker=odds.bookmaker,
            last_update=odds.fetched_at,
            outcomes=[
                GameOddsOutcomeOut(
                    outcome_key=outcome.outcome_key,
                    outcome_label=outcome.outcome_label,
                    price_american=outcome.price_american,
                    team_side=outcome.team_side,
                )
                for outcome in odds.outcomes
            ],
        )

    return game_views
