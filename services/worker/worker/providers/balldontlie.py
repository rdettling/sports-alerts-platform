from __future__ import annotations

from datetime import UTC, datetime
import logging
from time import monotonic
from typing import Any, Callable

import httpx

from app.services.api_usage import record_api_call_event
from sqlalchemy.orm import Session
from worker.providers.base import ProviderGame, ScoreboardRequest, SportsProvider

logger = logging.getLogger(__name__)

SCOREBOARD_URLS = {
    "NBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "MLB": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
}
class BallDontLieProvider(SportsProvider):
    def __init__(self, fetch_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None):
        self._fetch_json = fetch_json or self._default_fetch_json
        self._telemetry_db: Session | None = None
        self._ingest_run_id: int | None = None

    def set_telemetry_context(self, db: Session | None, ingest_run_id: int | None) -> None:
        self._telemetry_db = db
        self._ingest_run_id = ingest_run_id

    def _default_fetch_json(self, league: str, params: dict[str, str]) -> dict[str, Any]:
        scoreboard_url = SCOREBOARD_URLS.get(league.upper())
        if not scoreboard_url:
            raise ValueError(f"Unsupported league for ESPN scoreboard: {league}")
        started_at = monotonic()
        response = httpx.get(scoreboard_url, params=params, timeout=15.0)
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

    def _parse_event(self, league: str, event: dict[str, Any]) -> ProviderGame | None:
        competition = (event.get("competitions") or [{}])[0]
        notes = competition.get("notes") or []
        for note in notes:
            headline = str(note.get("headline") or "").lower()
            if "if necessary" in headline:
                return None

        competitors = competition.get("competitors") or []
        if len(competitors) < 2:
            return None

        home = next((team for team in competitors if team.get("homeAway") == "home"), None)
        away = next((team for team in competitors if team.get("homeAway") == "away"), None)
        if not home or not away:
            return None

        home_team = home.get("team") or {}
        away_team = away.get("team") or {}
        home_external_team_id = str(home_team.get("id") or "").strip()
        away_external_team_id = str(away_team.get("id") or "").strip()
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

        status_payload = competition.get("status", {}) or {}
        period = status_payload.get("period")
        clock = status_payload.get("displayClock")
        if league.upper() == "MLB":
            short_detail = str(status_type.get("shortDetail") or "").strip()
            # ESPN shortDetail carries half-inning context (e.g. "Top 6th", "Bot 7th").
            if short_detail:
                clock = short_detail
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

    def _fetch_events_for_dates(self, league: str, dates: list[str]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for date in dates:
            try:
                payload = self._fetch_json(league, {"dates": date})
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

    def fetch_games(self, league: str, requests: list[ScoreboardRequest]) -> list[ProviderGame]:
        if not requests:
            today = datetime.now(UTC).date().strftime("%Y%m%d")
            request_dates = [today]
        else:
            request_dates = sorted({request.date for request in requests})
        events = self._fetch_events_for_dates(league, request_dates)
        games = [self._parse_event(league, event) for event in events]
        return [game for game in games if game]

    def expected_call_count(self, requests: list[ScoreboardRequest]) -> int:
        if not requests:
            return 1
        return len({request.date for request in requests})
