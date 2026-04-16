from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOddsCurrent
from worker.config import settings
from worker.providers.base import EspnRequest


@dataclass(frozen=True)
class FetchPlan:
    mode: str
    next_ingest_seconds: int
    espn_requests: list[EspnRequest]
    odds_refresh: bool
    odds_refresh_reason: str
    expected_espn_calls: int
    expected_odds_calls: int


def _pick_mode(db: Session, now: datetime) -> str:
    live_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
            Game.is_final.is_(False),
            Game.status.in_(("in_progress", "live")),
        )
    ) or 0
    if live_count > 0:
        return "live"

    active_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
            Game.is_final.is_(False),
            or_(
                Game.status == "scheduled",
                Game.scheduled_start_time >= now - timedelta(hours=6),
            ),
            Game.scheduled_start_time <= now + timedelta(hours=24),
        )
    ) or 0
    if active_count > 0:
        return "active"

    return "idle"


def _mode_interval_seconds(mode: str) -> int:
    if mode == "live":
        return max(15, settings.ingest_interval_live_seconds)
    if mode == "active":
        return max(30, settings.ingest_interval_active_seconds)
    return max(60, settings.ingest_interval_idle_seconds)


def _tracked_dates(db: Session, now: datetime) -> set[str]:
    rows = db.execute(
        select(Game.scheduled_start_time, Game.status).where(
            Game.league == "NBA",
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


def _default_dates_for_mode(mode: str, now: datetime) -> set[str]:
    today = now.date()
    if mode == "live":
        return {
            (today - timedelta(days=1)).strftime("%Y%m%d"),
            today.strftime("%Y%m%d"),
        }
    if mode == "active":
        return {
            today.strftime("%Y%m%d"),
            (today + timedelta(days=1)).strftime("%Y%m%d"),
        }
    return {today.strftime("%Y%m%d")}


def _build_espn_requests(db: Session, mode: str, now: datetime) -> list[EspnRequest]:
    dates = _default_dates_for_mode(mode, now)
    dates.update(_tracked_dates(db, now))
    return [EspnRequest(date=value) for value in sorted(dates)]


def _odds_refresh_decision(db: Session, now: datetime) -> tuple[bool, str]:
    if not settings.odds_enabled:
        return False, "disabled"

    relevant_games = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
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

    last_fetched = db.scalar(
        select(func.max(GameOddsCurrent.fetched_at)).where(
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == settings.odds_api_market,
        )
    )
    if last_fetched is None:
        return True, "never_fetched"

    fetched_at = last_fetched if last_fetched.tzinfo else last_fetched.replace(tzinfo=timezone.utc)
    age_seconds = (now - fetched_at).total_seconds()
    if age_seconds >= settings.odds_refresh_seconds:
        return True, "stale_cache"
    return False, "fresh_cache"


def build_fetch_plan(db: Session, now: datetime | None = None) -> FetchPlan:
    at = now or datetime.now(timezone.utc)
    mode = _pick_mode(db, at)
    requests = _build_espn_requests(db, mode, at)
    odds_refresh, odds_reason = _odds_refresh_decision(db, at)
    return FetchPlan(
        mode=mode,
        next_ingest_seconds=_mode_interval_seconds(mode),
        espn_requests=requests,
        odds_refresh=odds_refresh,
        odds_refresh_reason=odds_reason,
        expected_espn_calls=len(requests),
        expected_odds_calls=1 if odds_refresh else 0,
    )
