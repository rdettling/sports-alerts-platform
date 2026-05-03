from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOddsCurrent, SentAlert, UserGameFollow
from worker.config import settings


def retention_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    at = now or datetime.now(timezone.utc)
    lower = at - timedelta(hours=max(1, settings.games_retention_past_hours))
    upper = at + timedelta(days=max(1, settings.games_retention_future_days))
    return lower, upper


def cleanup_games_outside_window(db: Session, now: datetime | None = None) -> int:
    lower, upper = retention_window(now)
    game_ids = db.scalars(
        select(Game.id).where(
            (Game.scheduled_start_time < lower) | (Game.scheduled_start_time > upper)
        )
    ).all()
    if not game_ids:
        return 0

    db.execute(delete(SentAlert).where(SentAlert.game_id.in_(game_ids)))
    db.execute(delete(UserGameFollow).where(UserGameFollow.game_id.in_(game_ids)))
    db.execute(delete(GameOddsCurrent).where(GameOddsCurrent.game_id.in_(game_ids)))
    db.execute(delete(Game).where(Game.id.in_(game_ids)))
    return len(game_ids)
