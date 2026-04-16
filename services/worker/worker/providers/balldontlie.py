from __future__ import annotations

from datetime import UTC, datetime
import logging
from time import monotonic
from typing import Any, Callable

import httpx

from app.services.api_usage import record_api_call_event
from sqlalchemy.orm import Session
from worker.providers.base import EspnRequest, NbaProvider, ProviderGame

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ABBR_TO_EXTERNAL_TEAM_ID = {
    "ATL": "1610612737",
    "BOS": "1610612738",
    "BKN": "1610612751",
    "CHA": "1610612766",
    "CHI": "1610612741",
    "CLE": "1610612739",
    "DAL": "1610612742",
    "DEN": "1610612743",
    "DET": "1610612765",
    "GSW": "1610612744",
    "HOU": "1610612745",
    "IND": "1610612754",
    "LAC": "1610612746",
    "LAL": "1610612747",
    "MEM": "1610612763",
    "MIA": "1610612748",
    "MIL": "1610612749",
    "MIN": "1610612750",
    "NOP": "1610612740",
    "NYK": "1610612752",
    "OKC": "1610612760",
    "ORL": "1610612753",
    "PHI": "1610612755",
    "PHX": "1610612756",
    "POR": "1610612757",
    "SAC": "1610612758",
    "SAS": "1610612759",
    "TOR": "1610612761",
    "UTA": "1610612762",
    "WAS": "1610612764",
    "GS": "1610612744",
    "NO": "1610612740",
    "SA": "1610612759",
    "NY": "1610612752",
}


class BallDontLieProvider(NbaProvider):
    def __init__(self, fetch_json: Callable[[dict[str, str]], dict[str, Any]] | None = None):
        self._fetch_json = fetch_json or self._default_fetch_json
        self._telemetry_db: Session | None = None
        self._ingest_run_id: int | None = None

    def set_telemetry_context(self, db: Session | None, ingest_run_id: int | None) -> None:
        self._telemetry_db = db
        self._ingest_run_id = ingest_run_id

    def _default_fetch_json(self, params: dict[str, str]) -> dict[str, Any]:
        started_at = monotonic()
        response = httpx.get(SCOREBOARD_URL, params=params, timeout=15.0)
        status_code = int(response.status_code)
        if self._telemetry_db is not None:
            record_api_call_event(
                self._telemetry_db,
                service="worker",
                provider="espn",
                endpoint_key="scoreboard",
                attempt_status="rate_limited" if status_code == 429 else ("success" if 200 <= status_code < 300 else "error"),
                http_status=status_code,
                latency_ms=int((monotonic() - started_at) * 1000),
                ingest_run_id=self._ingest_run_id,
            )
        response.raise_for_status()
        return response.json()

    def _parse_event(self, event: dict[str, Any]) -> ProviderGame | None:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        if len(competitors) < 2:
            return None

        home = next((team for team in competitors if team.get("homeAway") == "home"), None)
        away = next((team for team in competitors if team.get("homeAway") == "away"), None)
        if not home or not away:
            return None

        home_abbr = (((home.get("team") or {}).get("abbreviation")) or "").upper()
        away_abbr = (((away.get("team") or {}).get("abbreviation")) or "").upper()
        home_external_team_id = ABBR_TO_EXTERNAL_TEAM_ID.get(home_abbr)
        away_external_team_id = ABBR_TO_EXTERNAL_TEAM_ID.get(away_abbr)
        if not home_external_team_id or not away_external_team_id:
            return None

        status_type = ((competition.get("status") or {}).get("type") or {})
        status_state = status_type.get("state", "")
        status_name = status_type.get("name", "")
        status = "scheduled"
        if status_state == "in":
            status = "in_progress"
        elif status_state == "post":
            status = "final"
        elif status_name.lower() == "postponed":
            status = "postponed"

        game_date = event.get("date")
        if not game_date:
            return None
        scheduled_start_time = datetime.fromisoformat(game_date.replace("Z", "+00:00"))

        period = competition.get("status", {}).get("period")
        clock = competition.get("status", {}).get("displayClock")
        completed = bool(status_type.get("completed"))

        return ProviderGame(
            external_game_id=str(event.get("id")),
            home_external_team_id=home_external_team_id,
            away_external_team_id=away_external_team_id,
            scheduled_start_time=scheduled_start_time,
            status=status,
            home_score=int(home.get("score")) if home.get("score") else None,
            away_score=int(away.get("score")) if away.get("score") else None,
            period=int(period) if period else None,
            clock=clock if clock else None,
            is_final=status == "final" and completed,
        )

    def _fetch_events_for_dates(self, dates: list[str]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for date in dates:
            try:
                payload = self._fetch_json({"dates": date})
            except Exception:  # pragma: no cover - exercised through integration behavior
                # Keep existing game rows when a targeted request fails; retry next planner tick.
                # This prevents widening to a broad fallback request in the same cycle.
                logger.warning("ESPN request failed for date=%s; preserving stale game rows until next cycle", date)
                continue
            for event in payload.get("events", []):
                event_id = str(event.get("id"))
                if event_id:
                    by_id[event_id] = event
        return list(by_id.values())

    def fetch_games(self, requests: list[EspnRequest]) -> list[ProviderGame]:
        if not requests:
            today = datetime.now(UTC).date().strftime("%Y%m%d")
            request_dates = [today]
        else:
            request_dates = sorted({request.date for request in requests})
        events = self._fetch_events_for_dates(request_dates)
        games = [self._parse_event(event) for event in events]
        return [game for game in games if game]

    def expected_call_count(self, requests: list[EspnRequest]) -> int:
        if not requests:
            return 1
        return len({request.date for request in requests})
