from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Game, GameOddsCurrent
from app.db.session import SessionLocal
from app.db.usage import record_activity
from app.schemas.game import GameOddsOut, GameOddsOutcomeOut, GameOut
from app.services.competitions import get_active_competitions, normalize_competition
from app.services.game_views import build_game_outs

GAMES_RETENTION_PAST_HOURS = 36
GAMES_RETENTION_FUTURE_DAYS = 7


def load_games(
    db: Session,
    *,
    status: str | None = None,
    competition: str | None = None,
    include_finals: bool = False,
    limit: int = 50,
) -> list[GameOut]:
    active_competitions = get_active_competitions(db)
    now = datetime.now(timezone.utc)
    lower = now - timedelta(hours=GAMES_RETENTION_PAST_HOURS)
    upper = now + timedelta(days=GAMES_RETENTION_FUTURE_DAYS)
    stmt = (
        select(Game)
        .where(Game.competition.in_(active_competitions))
        .where(Game.scheduled_start_time >= lower, Game.scheduled_start_time <= upper)
        .order_by(Game.scheduled_start_time.asc())
        .limit(limit)
    )
    if competition:
        stmt = stmt.where(Game.competition == normalize_competition(competition))
    if status:
        stmt = stmt.where(Game.status == status)
    elif not include_finals:
        stmt = stmt.where(Game.is_final.is_(False))
    games = db.scalars(stmt).all()
    game_views = build_game_outs(db, games)
    if not games:
        return game_views

    game_ids = [game.id for game in games]
    odds_rows = db.scalars(
        select(GameOddsCurrent)
        .options(selectinload(GameOddsCurrent.outcomes))
        .where(GameOddsCurrent.game_id.in_(game_ids))
    ).all()
    odds_by_game_id = {row.game_id: row for row in odds_rows}

    for game_view in game_views:
        odds = odds_by_game_id.get(game_view.id)
        if not odds:
            continue
        game_view.odds = GameOddsOut(
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


class GameFeedCache:
    def __init__(self) -> None:
        self._state_lock = Lock()
        self._fill_lock = Lock()
        self._generation = 0
        self._expires_at = 0.0
        self._games: list[GameOut] | None = None

    def invalidate(self) -> None:
        with self._state_lock:
            self._generation += 1
            self._games = None

    def get(self) -> list[GameOut]:
        with self._state_lock:
            if self._games is not None and monotonic() < self._expires_at:
                record_activity("game_cache_hits")
                return self._games

        with self._fill_lock:
            while True:
                with self._state_lock:
                    if self._games is not None and monotonic() < self._expires_at:
                        record_activity("game_cache_hits")
                        return self._games
                    generation = self._generation
                record_activity("game_cache_fills")
                started_at = monotonic()
                with SessionLocal() as db:
                    games = load_games(db, include_finals=True, limit=500)
                with self._state_lock:
                    # Invalidation can arrive while the database read is in flight.
                    if generation != self._generation:
                        record_activity("game_cache_discarded_fills")
                        continue
                    self._games = games
                    self._expires_at = started_at + 30
                    return games


game_feed_cache = GameFeedCache()
