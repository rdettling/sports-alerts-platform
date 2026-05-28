from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOddsCurrent
from worker.config import settings
from worker.providers.base import ScoreboardRequest

INGEST_LIVE_INTERVAL_SECONDS = 120
INGEST_PREGAME_HOT_INTERVAL_SECONDS = 900
INGEST_PREGAME_COLD_INTERVAL_SECONDS = 3600
INGEST_OFF_INTERVAL_SECONDS = 43200
INGEST_PREGAME_HOT_WINDOW_MINUTES = 90
INGEST_PREGAME_COLD_WINDOW_HOURS = 24
INGEST_COLD_START_LOOKBACK_DAYS = 2
INGEST_COLD_START_LOOKAHEAD_DAYS = 7
INGEST_LIVE_SYNC_LOOKBACK_HOURS = 2
INGEST_LIVE_SYNC_LOOKAHEAD_HOURS = 6


@dataclass(frozen=True)
class FetchPlan:
    mode: str
    next_ingest_seconds: int
    espn_requests: list[ScoreboardRequest]
    odds_refresh: bool
    odds_refresh_reason: str
    expected_espn_calls: int
    expected_odds_calls: int


def _pick_mode(db: Session, now: datetime, league: str) -> str:
    live_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status.in_(("in_progress", "live")),
        )
    ) or 0
    if live_count > 0:
        return "live"

    next_scheduled = db.scalar(
        select(func.min(Game.scheduled_start_time)).where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now,
        )
    )
    if next_scheduled is not None:
        next_start = next_scheduled if next_scheduled.tzinfo else next_scheduled.replace(tzinfo=timezone.utc)
        delta_seconds = (next_start - now).total_seconds()
        if delta_seconds <= max(60, INGEST_PREGAME_HOT_WINDOW_MINUTES * 60):
            return "pregame_hot"
        if delta_seconds <= max(3600, INGEST_PREGAME_COLD_WINDOW_HOURS * 3600):
            return "pregame_cold"

    return "off"


def _mode_interval_seconds(mode: str) -> int:
    if mode == "live":
        return max(15, INGEST_LIVE_INTERVAL_SECONDS)
    if mode == "pregame_hot":
        return max(60, INGEST_PREGAME_HOT_INTERVAL_SECONDS)
    if mode == "pregame_cold":
        return max(300, INGEST_PREGAME_COLD_INTERVAL_SECONDS)
    return max(900, INGEST_OFF_INTERVAL_SECONDS)


def _tracked_dates(db: Session, now: datetime, league: str) -> set[str]:
    rows = db.execute(
        select(Game.scheduled_start_time, Game.status).where(
            Game.league == league,
            Game.is_final.is_(False),
            or_(
                Game.status.in_(("in_progress", "live")),
                and_(
                    Game.scheduled_start_time >= now - timedelta(hours=6),
                    Game.scheduled_start_time <= now + timedelta(hours=36),
                ),
            ),
        )
    ).all()
    dates: set[str] = set()
    for start_time, _status in rows:
        dt = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        dates.add(dt.strftime("%Y%m%d"))
    return dates


def _default_dates_for_mode(_mode: str, now: datetime) -> set[str]:
    today = now.date()
    return {
        (today - timedelta(days=1)).strftime("%Y%m%d"),
        today.strftime("%Y%m%d"),
        (today + timedelta(days=1)).strftime("%Y%m%d"),
    }


def _cold_start_dates(now: datetime) -> set[str]:
    today = now.date()
    lookback = max(0, INGEST_COLD_START_LOOKBACK_DAYS)
    lookahead = max(0, INGEST_COLD_START_LOOKAHEAD_DAYS)
    return {
        (today + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(-lookback, lookahead + 1)
    }


def _is_cold_start(db: Session, league: str) -> bool:
    existing_games = db.scalar(select(func.count(Game.id)).where(Game.league == league)) or 0
    return existing_games == 0


def _build_espn_requests(db: Session, mode: str, now: datetime, league: str) -> list[ScoreboardRequest]:
    dates = _default_dates_for_mode(mode, now)
    tracked_dates = _tracked_dates(db, now, league)
    dates.update(tracked_dates)
    if not tracked_dates and _is_cold_start(db, league):
        dates.update(_cold_start_dates(now))
    return [ScoreboardRequest(date=value) for value in sorted(dates)]


def _odds_refresh_decision(db: Session, now: datetime, league: str) -> tuple[bool, str]:
    if not settings.odds_enabled:
        return False, "disabled"

    relevant_games = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == league,
            Game.is_final.is_(False),
            or_(
                Game.status.in_(("in_progress", "live")),
                and_(
                    Game.status == "scheduled",
                    Game.scheduled_start_time >= now - timedelta(hours=1),
                    Game.scheduled_start_time <= now + timedelta(hours=24),
                ),
            ),
        )
    ) or 0
    if relevant_games == 0:
        return False, "no_relevant_games"

    # Snapshot-only policy: only fetch when at least one relevant game has no stored snapshot.
    missing_snapshot_count = db.scalar(
        select(func.count(Game.id))
        .outerjoin(
            GameOddsCurrent,
            and_(
                GameOddsCurrent.game_id == Game.id,
                GameOddsCurrent.provider == settings.odds_provider,
                GameOddsCurrent.market == settings.odds_api_market,
            ),
        )
        .where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now,
            Game.scheduled_start_time <= now + timedelta(hours=max(1, settings.odds_pregame_window_hours)),
            GameOddsCurrent.id.is_(None),
        )
    ) or 0
    if missing_snapshot_count > 0:
        return True, "missing_snapshots"
    return False, "snapshots_present"


def build_fetch_plan(db: Session, league: str, now: datetime | None = None) -> FetchPlan:
    at = now or datetime.now(timezone.utc)
    mode = _pick_mode(db, at, league)
    requests = _build_espn_requests(db, mode, at, league)
    odds_refresh, odds_reason = _odds_refresh_decision(db, at, league)
    return FetchPlan(
        mode=mode,
        next_ingest_seconds=_mode_interval_seconds(mode),
        espn_requests=requests,
        odds_refresh=odds_refresh,
        odds_refresh_reason=odds_reason,
        expected_espn_calls=len(requests),
        expected_odds_calls=1 if odds_refresh else 0,
    )


def build_catalog_requests(db: Session, league: str, now: datetime | None = None) -> list[ScoreboardRequest]:
    at = now or datetime.now(timezone.utc)
    return _build_espn_requests(db, "off", at, league)


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
    # Include current day to absorb provider status lag around day boundaries.
    dates.add(at.strftime("%Y%m%d"))
    return [ScoreboardRequest(date=value) for value in sorted(dates)]
