from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from app.services.api_usage import record_api_call_event
from app.services.leagues import get_league_profile, get_scoreboard_url

logger = logging.getLogger(__name__)


@dataclass
class ScoreboardGame:
    external_game_id: str
    home_external_team_id: str
    away_external_team_id: str
    scheduled_start_time: datetime
    status: str
    context_label: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    clock: str | None = None
    is_final: bool = False


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _format_world_cup_stage(slug: str | None) -> str | None:
    if not slug:
        return None
    mapping = {
        "group-stage": "Group Stage",
        "round-of-32": "Round of 32",
        "rd-of-16": "Round of 16",
        "quarterfinals": "Quarterfinals",
        "semifinals": "Semifinals",
        "3rd-place-match": "3rd-Place Match",
        "final": "Final",
    }
    return mapping.get(slug)


class EspnScoreboardClient:
    def __init__(self, fetch_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None):
        self._fetch_json = fetch_json or self._default_fetch_json
        self._telemetry_db: Session | None = None
        self._ingest_run_id: int | None = None

    def set_telemetry_context(self, db: Session | None, ingest_run_id: int | None) -> None:
        self._telemetry_db = db
        self._ingest_run_id = ingest_run_id

    def _default_fetch_json(self, league: str, params: dict[str, str]) -> dict[str, Any]:
        scoreboard_url = get_scoreboard_url(league)
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

    def _parse_event(self, league: str, event: dict[str, Any]) -> ScoreboardGame | None:
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
        if home_external_team_id.startswith("-") or away_external_team_id.startswith("-"):
            return None

        status_type = ((competition.get("status") or {}).get("type") or {})
        status_state = status_type.get("state", "")
        status_name = status_type.get("name", "")
        status_description = str(status_type.get("description") or "").lower()
        status = "scheduled"
        if "postponed" in status_name.lower() or status_description == "postponed":
            status = "postponed"
        elif status_state == "in":
            status = "in_progress"
        elif status_state == "post":
            status = "final"

        game_date = event.get("date")
        if not game_date:
            return None
        scheduled_start_time = datetime.fromisoformat(game_date.replace("Z", "+00:00"))

        status_payload = competition.get("status", {}) or {}
        period = status_payload.get("period")
        clock = status_payload.get("displayClock")
        short_detail = str(status_type.get("shortDetail") or "").strip()
        normalized_league = league.upper()
        sport = get_league_profile(normalized_league).sport
        if sport in {"baseball", "soccer"} and short_detail:
            clock = short_detail
        completed = bool(status_type.get("completed"))
        context_label: str | None = None
        if normalized_league == "NBA":
            round_label = _clean_text(((competition.get("notes") or [{}])[0]).get("headline"))
            series_summary = _clean_text(((competition.get("series") or {}).get("summary")))
            context_label = f"{round_label} · {series_summary}" if round_label and series_summary else round_label or series_summary
        elif normalized_league == "WORLD_CUP":
            season = event.get("season") or {}
            season_slug = _clean_text(season.get("slug"))
            season_type = season.get("type")
            season_type_name = _clean_text(season_type.get("name")) if isinstance(season_type, dict) else None
            context_label = _format_world_cup_stage(season_slug) or season_type_name

        return ScoreboardGame(
            external_game_id=str(event.get("id")),
            home_external_team_id=home_external_team_id,
            away_external_team_id=away_external_team_id,
            scheduled_start_time=scheduled_start_time,
            context_label=context_label,
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
            except Exception:  # pragma: no cover
                logger.warning("ESPN request failed for date=%s; preserving stale game rows until next cycle", date)
                continue
            for event in payload.get("events", []):
                event_id = str(event.get("id"))
                if event_id:
                    by_id[event_id] = event
        return list(by_id.values())

    def fetch_games(self, league: str, dates: list[str]) -> list[ScoreboardGame]:
        request_dates = sorted(set(dates)) or [datetime.now(UTC).date().strftime("%Y%m%d")]
        events = self._fetch_events_for_dates(league, request_dates)
        games = [self._parse_event(league, event) for event in events]
        return [game for game in games if game]
