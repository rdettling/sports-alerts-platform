from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LeagueSetting

LEAGUE_ORDER = ("NBA", "MLB")
ALERT_TYPES_BY_LEAGUE = {
    "NBA": ["game_start", "close_game_late", "final_result"],
    "MLB": ["game_start", "inning_start", "final_result"],
}
DEFAULT_TEST_MATCHUPS_BY_LEAGUE = {
    "NBA": ("ATL", "BOS"),
    "MLB": ("MIA", "TOR"),
}


def normalize_league(league: str) -> str:
    value = league.strip().upper()
    if value not in LEAGUE_ORDER:
        raise ValueError(f"Unsupported league: {league}")
    return value


def ensure_league_settings(db: Session) -> None:
    existing = {
        row.league
        for row in db.scalars(select(LeagueSetting).where(LeagueSetting.league.in_(LEAGUE_ORDER))).all()
    }
    if len(existing) == len(LEAGUE_ORDER):
        return

    now = datetime.now(timezone.utc)
    for league in LEAGUE_ORDER:
        if league in existing:
            continue
        db.add(LeagueSetting(league=league, is_enabled=True, created_at=now, updated_at=now))
    db.commit()


def list_league_settings(db: Session) -> list[LeagueSetting]:
    ensure_league_settings(db)
    rows = db.scalars(select(LeagueSetting).order_by(LeagueSetting.league.asc())).all()
    order = {league: index for index, league in enumerate(LEAGUE_ORDER)}
    return sorted(rows, key=lambda row: order.get(row.league, len(order)))


def get_active_leagues(db: Session) -> list[str]:
    return [row.league for row in list_league_settings(db) if row.is_enabled]


def is_league_enabled(db: Session, league: str) -> bool:
    normalized = normalize_league(league)
    return normalized in set(get_active_leagues(db))
