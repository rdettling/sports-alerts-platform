from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen

from worker.config import settings

logger = logging.getLogger(__name__)

TEAM_NAME_ALIASES = {
    "la clippers": "los angeles clippers",
}

_CACHE_LOCK = threading.Lock()
_CACHE_FETCHED_AT = 0.0
_CACHE_DATA: dict[tuple[str, str], "MoneylineOdds"] = {}


@dataclass(frozen=True)
class MoneylineOdds:
    home_moneyline: int | None
    away_moneyline: int | None
    bookmaker: str | None
    last_update: datetime | None


def _normalize_team_name(name: str) -> str:
    cleaned = " ".join(name.strip().lower().split())
    return TEAM_NAME_ALIASES.get(cleaned, cleaned)


def game_key(home_team_name: str, away_team_name: str) -> tuple[str, str]:
    return (_normalize_team_name(home_team_name), _normalize_team_name(away_team_name))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_event_moneyline(event: dict) -> MoneylineOdds | None:
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
            if not isinstance(market, dict) or market.get("key") != settings.odds_api_market:
                continue
            outcomes = market.get("outcomes")
            if not isinstance(outcomes, list):
                continue
            prices_by_team: dict[str, int] = {}
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                outcome_name = _normalize_team_name(str(outcome.get("name", "")))
                price = outcome.get("price")
                if isinstance(price, int):
                    prices_by_team[outcome_name] = price
            if not prices_by_team:
                continue
            return MoneylineOdds(
                home_moneyline=prices_by_team.get(home_name),
                away_moneyline=prices_by_team.get(away_name),
                bookmaker=bookmaker.get("title") if isinstance(bookmaker, dict) else None,
                last_update=_parse_datetime(bookmaker.get("last_update") if isinstance(bookmaker, dict) else None),
            )
    return None


def _fetch_from_provider() -> dict[tuple[str, str], MoneylineOdds]:
    query = urlencode(
        {
            "apiKey": settings.odds_api_key,
            "regions": settings.odds_api_regions,
            "markets": settings.odds_api_market,
            "oddsFormat": settings.odds_api_format,
        }
    )
    url = f"{settings.odds_api_base_url.rstrip('/')}/{settings.odds_api_sport_key}/odds?{query}"

    with urlopen(url, timeout=settings.odds_api_timeout_seconds) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        return {}

    odds_index: dict[tuple[str, str], MoneylineOdds] = {}
    for event in payload:
        if not isinstance(event, dict):
            continue
        home_name = _normalize_team_name(str(event.get("home_team", "")))
        away_name = _normalize_team_name(str(event.get("away_team", "")))
        if not home_name or not away_name:
            continue
        odds = _extract_event_moneyline(event)
        if odds:
            odds_index[(home_name, away_name)] = odds
    return odds_index


def fetch_nba_odds_index() -> dict[tuple[str, str], MoneylineOdds]:
    global _CACHE_FETCHED_AT, _CACHE_DATA  # noqa: PLW0603

    now = monotonic()
    with _CACHE_LOCK:
        if _CACHE_DATA and now - _CACHE_FETCHED_AT < settings.odds_api_cache_seconds:
            return _CACHE_DATA

    try:
        fresh_data = _fetch_from_provider()
    except Exception as exc:
        logger.warning("Odds API request failed: %s", exc)
        return {}

    with _CACHE_LOCK:
        _CACHE_DATA = fresh_data
        _CACHE_FETCHED_AT = monotonic()
        return _CACHE_DATA
