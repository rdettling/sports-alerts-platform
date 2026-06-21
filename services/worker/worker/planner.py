from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Game
from worker.providers.base import ScoreboardRequest

INGEST_CATALOG_LOOKBACK_DAYS = 1
INGEST_CATALOG_LOOKAHEAD_DAYS = 7
INGEST_LIVE_SYNC_LOOKBACK_HOURS = 2
INGEST_LIVE_SYNC_LOOKAHEAD_HOURS = 6

def _default_catalog_dates(now: datetime) -> set[str]:
    today = now.date()
    return {
        (today + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(-max(0, INGEST_CATALOG_LOOKBACK_DAYS), max(0, INGEST_CATALOG_LOOKAHEAD_DAYS) + 1)
    }


def _build_catalog_requests(now: datetime) -> list[ScoreboardRequest]:
    dates = _default_catalog_dates(now)
    return [ScoreboardRequest(date=value) for value in sorted(dates)]


def build_catalog_requests(db: Session, league: str, now: datetime | None = None) -> list[ScoreboardRequest]:
    at = now or datetime.now(timezone.utc)
    return _build_catalog_requests(at)


def build_live_requests(db: Session, league: str, now: datetime | None = None) -> list[ScoreboardRequest]:
    at = now or datetime.now(timezone.utc)
    candidate_rows = db.execute(
        select(Game.scheduled_start_time).where(
            Game.league == league,
            Game.is_final.is_(False),
            or_(
                Game.status.in_(("in_progress", "live")),
                and_(
                    Game.status == "scheduled",
                    Game.scheduled_start_time >= at - timedelta(hours=INGEST_LIVE_SYNC_LOOKBACK_HOURS),
                    Game.scheduled_start_time <= at + timedelta(hours=INGEST_LIVE_SYNC_LOOKAHEAD_HOURS),
                ),
            ),
        )
    ).all()
    if not candidate_rows:
        return []
    dates = {
        (start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)).strftime("%Y%m%d")
        for start_time, in candidate_rows
    }
    # ESPN can bucket late-evening U.S. games under the previous scoreboard date
    # even when their UTC start spills into the next day.
    dates.add((at - timedelta(days=1)).strftime("%Y%m%d"))
    # Include current day to absorb provider status lag around day boundaries.
    dates.add(at.strftime("%Y%m%d"))
    return [ScoreboardRequest(date=value) for value in sorted(dates)]
