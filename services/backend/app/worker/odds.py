from __future__ import annotations

import json
import logging
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOddsCurrent, GameOddsOutcomeCurrent
from app.services.leagues import get_league_profile
from app.worker.config import settings

logger = logging.getLogger(__name__)
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"
ODDS_API_REGION = "us"
ODDS_MARKET = "h2h"
ODDS_FORMAT = "american"
ODDS_TIMEOUT_SECONDS = 6
ODDS_CACHE_SECONDS = 60
ODDS_PREGAME_WINDOW = timedelta(hours=24)
MATCH_MAX_COMMENCE_DIFF = timedelta(hours=18)

TEAM_NAME_ALIASES = {
    "la clippers": "los angeles clippers",
    "bosnia and herzegovina": "bosnia herzegovina",
    "chicago fire fc": "chicago fire",
    "columbus crew": "columbus crew sc",
    "czech republic": "czechia",
    "dr congo": "congo dr",
    "houston dynamo fc": "houston dynamo",
    "lafc": "los angeles fc",
    "red bull new york": "new york red bulls",
    "turkey": "turkiye",
    "usa": "united states",
    "vancouver whitecaps": "vancouver whitecaps fc",
}

_CACHE_LOCK = threading.Lock()
_CACHE_FETCHED_AT_BY_LEAGUE: dict[str, float] = {}
_CACHE_DATA_BY_LEAGUE: dict[str, dict[tuple[str, str], list[OddsSnapshot]]] = {}


@dataclass(frozen=True)
class OddsOutcome:
    outcome_key: str
    outcome_label: str
    outcome_order: int
    price_american: int | None
    team_side: str | None


@dataclass(frozen=True)
class OddsSnapshot:
    outcomes: tuple[OddsOutcome, ...]
    bookmaker: str | None
    last_update: datetime | None
    commence_time: datetime | None = None


def _normalize_team_name(name: str) -> str:
    cleaned = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = cleaned.strip().lower().replace("&", "and").replace("-", " ")
    cleaned = "".join(character if character.isalnum() or character.isspace() else " " for character in cleaned)
    cleaned = " ".join(cleaned.split())
    return TEAM_NAME_ALIASES.get(cleaned, cleaned)


def game_key(home_team_name: str, away_team_name: str) -> tuple[str, str]:
    return (_normalize_team_name(home_team_name), _normalize_team_name(away_team_name))


def _odds_signature(odds: OddsSnapshot) -> tuple[tuple[str, str | None, int | None, str | None], ...]:
    return tuple(
        (outcome.outcome_key, outcome.team_side, outcome.price_american, outcome.outcome_label)
        for outcome in odds.outcomes
    )


def _stored_odds_signature(row: GameOddsCurrent) -> tuple[tuple[str, str | None, int | None, str | None], ...]:
    return tuple(
        (outcome.outcome_key, outcome.team_side, outcome.price_american, outcome.outcome_label)
        for outcome in sorted(row.outcomes, key=lambda outcome: outcome.outcome_order)
    )


def _build_current_outcomes(odds: OddsSnapshot) -> list[GameOddsOutcomeCurrent]:
    return [
        GameOddsOutcomeCurrent(
            outcome_key=outcome.outcome_key,
            outcome_label=outcome.outcome_label,
            outcome_order=outcome.outcome_order,
            price_american=outcome.price_american,
            team_side=outcome.team_side,
        )
        for outcome in odds.outcomes
    ]


def upsert_game_odds(db: Session, game_id: int, odds: OddsSnapshot) -> bool:
    row = db.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game_id))
    if row:
        before = (row.bookmaker, _stored_odds_signature(row))
        after = (odds.bookmaker, _odds_signature(odds))
        if before == after:
            return False
        row.bookmaker = odds.bookmaker
        row.fetched_at = odds.last_update or datetime.now(timezone.utc)
        row.outcomes.clear()
        row.outcomes.extend(_build_current_outcomes(odds))
        return True

    row = GameOddsCurrent(
        game_id=game_id,
        bookmaker=odds.bookmaker,
        fetched_at=odds.last_update or datetime.now(timezone.utc),
    )
    row.outcomes.extend(_build_current_outcomes(odds))
    db.add(row)
    return True


def select_best_for_game(
    options: list[OddsSnapshot] | OddsSnapshot | None,
    scheduled_start_time: datetime,
) -> OddsSnapshot | None:
    if options is None:
        return None
    candidates = options if isinstance(options, list) else [options]
    if not candidates:
        return None

    target = scheduled_start_time if scheduled_start_time.tzinfo else scheduled_start_time.replace(tzinfo=timezone.utc)
    with_commence = [odds for odds in candidates if odds.commence_time]
    if not with_commence:
        return candidates[0]

    closest = min(
        with_commence,
        key=lambda odds: abs(
            (
                (odds.commence_time if odds.commence_time.tzinfo else odds.commence_time.replace(tzinfo=timezone.utc))
                - target
            ).total_seconds()
        ),
    )
    closest_commence = (
        closest.commence_time
        if closest.commence_time.tzinfo
        else closest.commence_time.replace(tzinfo=timezone.utc)
    )
    if abs((closest_commence - target).total_seconds()) > MATCH_MAX_COMMENCE_DIFF.total_seconds():
        return None
    return closest


def games_missing_pregame_snapshot(
    db: Session,
    league: str,
    now: datetime,
    *,
    eligible_external_ids: set[str] | None = None,
) -> list[Game]:
    if eligible_external_ids is not None and not eligible_external_ids:
        return []
    pregame_cutoff = now + ODDS_PREGAME_WINDOW
    stmt = select(Game).where(
        Game.league == league,
        Game.is_final.is_(False),
        Game.status == "scheduled",
        Game.scheduled_start_time >= now,
        Game.scheduled_start_time <= pregame_cutoff,
    )
    if eligible_external_ids is not None:
        stmt = stmt.where(Game.external_game_id.in_(sorted(eligible_external_ids)))
    rows = db.scalars(stmt.order_by(Game.scheduled_start_time.asc())).all()
    if not rows:
        return []
    game_ids = [game.id for game in rows]
    existing_ids = {
        game_id
        for game_id, in db.execute(
            select(GameOddsCurrent.game_id).where(GameOddsCurrent.game_id.in_(game_ids))
        ).all()
    }
    return [game for game in rows if game.id not in existing_ids]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _outcome_key_from_name(name: str) -> str:
    normalized = _normalize_team_name(name)
    if normalized == "draw":
        return "draw"
    return normalized.replace(" ", "_")


def _extract_event_moneyline(event: dict) -> OddsSnapshot | None:
    home_name = _normalize_team_name(str(event.get("home_team", "")))
    away_name = _normalize_team_name(str(event.get("away_team", "")))
    if not home_name or not away_name:
        return None

    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        return None

    for bookmaker in bookmakers:
        markets = bookmaker.get("markets") if isinstance(bookmaker, dict) else None
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict) or market.get("key") != ODDS_MARKET:
                continue
            outcomes = market.get("outcomes")
            if not isinstance(outcomes, list):
                continue
            parsed_outcomes: list[OddsOutcome] = []
            for index, outcome in enumerate(outcomes):
                if not isinstance(outcome, dict):
                    continue
                raw_name = str(outcome.get("name", ""))
                outcome_name = _normalize_team_name(raw_name)
                price = outcome.get("price")
                team_side = None
                if outcome_name == away_name:
                    team_side = "away"
                elif outcome_name == home_name:
                    team_side = "home"
                parsed_outcomes.append(
                    OddsOutcome(
                        outcome_key=_outcome_key_from_name(raw_name),
                        outcome_label=raw_name,
                        outcome_order=index,
                        price_american=price if isinstance(price, int) else None,
                        team_side=team_side,
                    )
                )
            if not parsed_outcomes:
                continue
            return OddsSnapshot(
                outcomes=tuple(parsed_outcomes),
                bookmaker=bookmaker.get("title") if isinstance(bookmaker, dict) else None,
                last_update=_parse_datetime(bookmaker.get("last_update") if isinstance(bookmaker, dict) else None),
                commence_time=_parse_datetime(event.get("commence_time")),
            )
    return None


def _odds_sport_key_for_league(league: str) -> str:
    sport_key = get_league_profile(league).odds_sport_key
    if sport_key is None:
        raise ValueError(f"Odds are not supported for league: {league}")
    return sport_key


def _fetch_from_provider(league: str) -> dict[tuple[str, str], list[OddsSnapshot]]:
    query = urlencode(
        {
            "apiKey": settings.odds_api_key.strip(),
            "regions": ODDS_API_REGION,
            "markets": ODDS_MARKET,
            "oddsFormat": ODDS_FORMAT,
        }
    )
    sport_key = _odds_sport_key_for_league(league)
    url = f"{ODDS_API_BASE_URL}/{sport_key}/odds?{query}"

    with urlopen(url, timeout=ODDS_TIMEOUT_SECONDS) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, list):
        return {}

    odds_index: dict[tuple[str, str], list[OddsSnapshot]] = {}
    for event in payload:
        if not isinstance(event, dict):
            continue
        home_name = _normalize_team_name(str(event.get("home_team", "")))
        away_name = _normalize_team_name(str(event.get("away_team", "")))
        if not home_name or not away_name:
            continue
        odds = _extract_event_moneyline(event)
        if odds:
            key = (home_name, away_name)
            existing = odds_index.get(key, [])
            existing.append(odds)
            odds_index[key] = existing
    return odds_index


def fetch_odds_index(league: str) -> dict[tuple[str, str], list[OddsSnapshot]]:
    if not settings.odds_api_key.strip():
        return {}

    normalized = league.strip().upper()
    try:
        profile = get_league_profile(normalized)
    except ValueError:
        return {}
    if profile.odds_sport_key is None:
        return {}

    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE_DATA_BY_LEAGUE.get(normalized)
        fetched_at = _CACHE_FETCHED_AT_BY_LEAGUE.get(normalized, 0.0)
        if cached and now - fetched_at < ODDS_CACHE_SECONDS:
            return cached

    try:
        fresh_data = _fetch_from_provider(normalized)
    except Exception as exc:
        logger.warning("Odds API request failed: %s", exc)
        return {}

    with _CACHE_LOCK:
        _CACHE_DATA_BY_LEAGUE[normalized] = fresh_data
        _CACHE_FETCHED_AT_BY_LEAGUE[normalized] = monotonic()
        return _CACHE_DATA_BY_LEAGUE[normalized]
