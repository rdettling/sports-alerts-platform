from __future__ import annotations

import json
import logging
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.services.api_usage import record_api_call_event
from app.services.leagues import get_league_profile
from sqlalchemy.orm import Session
from worker.config import settings

logger = logging.getLogger(__name__)

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
_TELEMETRY_DB: Session | None = None


@dataclass(frozen=True)
class OddsOutcome:
    outcome_key: str
    outcome_label: str
    outcome_order: int
    price_american: int | None
    team_side: str | None


@dataclass(frozen=True)
class OddsSnapshot:
    market: str
    outcomes: tuple[OddsOutcome, ...]
    bookmaker: str | None
    last_update: datetime | None
    commence_time: datetime | None = None


def set_telemetry_context(db: Session | None) -> None:
    global _TELEMETRY_DB  # noqa: PLW0603
    _TELEMETRY_DB = db


def _normalize_team_name(name: str) -> str:
    cleaned = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = cleaned.strip().lower().replace("&", "and").replace("-", " ")
    cleaned = "".join(character if character.isalnum() or character.isspace() else " " for character in cleaned)
    cleaned = " ".join(cleaned.split())
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
            if not isinstance(market, dict) or market.get("key") != settings.odds_api_market:
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
                market=str(market.get("key", settings.odds_api_market)),
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
            "apiKey": settings.odds_api_key,
            "regions": settings.odds_api_regions,
            "markets": settings.odds_api_market,
            "oddsFormat": settings.odds_api_format,
        }
    )
    sport_key = _odds_sport_key_for_league(league)
    url = f"{settings.odds_api_base_url.rstrip('/')}/{sport_key}/odds?{query}"

    started_at = monotonic()
    try:
        with urlopen(url, timeout=settings.odds_api_timeout_seconds) as response:  # noqa: S310
            status_code = int(getattr(response, "status", 200))
            payload = json.loads(response.read().decode("utf-8"))
            if _TELEMETRY_DB is not None:
                record_api_call_event(
                    _TELEMETRY_DB,
                    service="worker",
                    provider="odds",
                    endpoint_key=settings.odds_api_market,
                    attempt_status="success" if 200 <= status_code < 300 else "error",
                    http_status=status_code,
                    latency_ms=int((monotonic() - started_at) * 1000),
                )
    except HTTPError as exc:
        if _TELEMETRY_DB is not None:
            record_api_call_event(
                _TELEMETRY_DB,
                service="worker",
                provider="odds",
                endpoint_key=settings.odds_api_market,
                attempt_status="rate_limited" if int(exc.code) == 429 else "error",
                http_status=int(exc.code),
                latency_ms=int((monotonic() - started_at) * 1000),
                error_code="http_error",
            )
        raise
    except URLError:
        if _TELEMETRY_DB is not None:
            record_api_call_event(
                _TELEMETRY_DB,
                service="worker",
                provider="odds",
                endpoint_key=settings.odds_api_market,
                attempt_status="error",
                latency_ms=int((monotonic() - started_at) * 1000),
                error_code="network_error",
            )
        raise
    except Exception:
        if _TELEMETRY_DB is not None:
            record_api_call_event(
                _TELEMETRY_DB,
                service="worker",
                provider="odds",
                endpoint_key=settings.odds_api_market,
                attempt_status="error",
                latency_ms=int((monotonic() - started_at) * 1000),
                error_code="unexpected_error",
            )
        raise

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
        if cached and now - fetched_at < settings.odds_api_cache_seconds:
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
