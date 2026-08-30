from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from app.services.competitions import get_competition_profile, get_scoreboard_url

logger = logging.getLogger(__name__)


@dataclass
class ScoreboardGame:
    external_game_id: str
    home_external_team_id: str
    away_external_team_id: str
    scheduled_start_time: datetime
    status: str
    home_team_name: str | None = None
    home_team_abbreviation: str | None = None
    away_team_name: str | None = None
    away_team_abbreviation: str | None = None
    season_slug: str | None = None
    season_week: int | None = None
    context_label: str | None = None
    home_team_record: str | None = None
    away_team_record: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    clock: str | None = None
    is_final: bool = False
    broadcast_names: list[str] = field(default_factory=list)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _total_record(competitor: dict[str, Any]) -> str | None:
    records = competitor.get("records")
    if not isinstance(records, list):
        return None
    total = next(
        (record for record in records if isinstance(record, dict) and record.get("type") == "total"),
        None,
    )
    return _clean_text(total.get("summary")) if total else None


def _broadcast_names(competition: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        name = _clean_text(value)
        if not name or name.casefold() in seen:
            return
        seen.add(name.casefold())
        names.append(name)

    broadcasts = competition.get("broadcasts")
    if isinstance(broadcasts, list):
        for broadcast in broadcasts:
            if not isinstance(broadcast, dict):
                continue
            values = broadcast.get("names")
            if isinstance(values, list):
                for value in values:
                    add(value)

    geo_broadcasts = competition.get("geoBroadcasts")
    if isinstance(geo_broadcasts, list):
        for broadcast in geo_broadcasts:
            if not isinstance(broadcast, dict):
                continue
            media = broadcast.get("media")
            if isinstance(media, dict):
                add(media.get("shortName"))

    return names


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

    def _default_fetch_json(self, competition: str, params: dict[str, str]) -> dict[str, Any]:
        scoreboard_url = get_scoreboard_url(competition)
        response = httpx.get(scoreboard_url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()

    def _parse_event(self, competition: str, event: dict[str, Any]) -> ScoreboardGame | None:
        event_competition = (event.get("competitions") or [{}])[0]
        notes = event_competition.get("notes") or []
        for note in notes:
            headline = str(note.get("headline") or "").lower()
            if "if necessary" in headline:
                return None

        competitors = event_competition.get("competitors") or []
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

        status_type = ((event_competition.get("status") or {}).get("type") or {})
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

        status_payload = event_competition.get("status", {}) or {}
        period = status_payload.get("period")
        clock = status_payload.get("displayClock")
        short_detail = str(status_type.get("shortDetail") or "").strip()
        normalized_competition = competition.upper()
        sport = get_competition_profile(normalized_competition).sport
        if sport in {"baseball", "soccer"} and short_detail:
            clock = short_detail
        completed = bool(status_type.get("completed"))
        season = event.get("season") or {}
        season_slug = _clean_text(season.get("slug"))
        week = event.get("week") or {}
        raw_season_week = week.get("number") if isinstance(week, dict) else None
        season_week = int(raw_season_week) if isinstance(raw_season_week, int) else None
        context_label: str | None = None
        if sport == "basketball":
            round_label = _clean_text(((event_competition.get("notes") or [{}])[0]).get("headline"))
            series_summary = _clean_text(((event_competition.get("series") or {}).get("summary")))
            context_label = f"{round_label} · {series_summary}" if round_label and series_summary else round_label or series_summary
        elif sport == "football":
            event_note = _clean_text(((event_competition.get("notes") or [{}])[0]).get("headline"))
            if event_note:
                context_label = event_note
            elif season_slug == "preseason":
                context_label = f"Preseason · Week {season_week}" if season_week is not None else "Preseason"
            elif season_slug == "post-season":
                context_label = "Postseason"
        elif normalized_competition == "WORLD_CUP":
            season_type = season.get("type")
            season_type_name = _clean_text(season_type.get("name")) if isinstance(season_type, dict) else None
            context_label = _format_world_cup_stage(season_slug) or season_type_name

        return ScoreboardGame(
            external_game_id=str(event.get("id")),
            home_external_team_id=home_external_team_id,
            away_external_team_id=away_external_team_id,
            scheduled_start_time=scheduled_start_time,
            home_team_name=_clean_text(home_team.get("displayName")),
            home_team_abbreviation=_clean_text(home_team.get("abbreviation")),
            away_team_name=_clean_text(away_team.get("displayName")),
            away_team_abbreviation=_clean_text(away_team.get("abbreviation")),
            season_slug=season_slug,
            season_week=season_week,
            context_label=context_label,
            home_team_record=_total_record(home),
            away_team_record=_total_record(away),
            status=status,
            home_score=int(home.get("score")) if home.get("score") else None,
            away_score=int(away.get("score")) if away.get("score") else None,
            period=int(period) if period else None,
            clock=clock if clock else None,
            is_final=status == "final" and completed,
            broadcast_names=_broadcast_names(event_competition),
        )

    def _fetch_events_for_dates(self, competition: str, dates: list[str]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        profile = get_competition_profile(competition)
        for date in dates:
            try:
                payload = self._fetch_json(
                    competition,
                    {**dict(profile.scoreboard_params), "dates": date},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "ESPN request failed competition=%s date=%s error=%s; preserving stale game rows until next cycle",
                    competition,
                    date,
                    exc,
                )
                continue
            for event in payload.get("events", []):
                event_id = str(event.get("id"))
                if event_id:
                    by_id[event_id] = event
        return list(by_id.values())

    def fetch_games(self, competition: str, dates: list[str]) -> list[ScoreboardGame]:
        request_dates = sorted(set(dates)) or [datetime.now(UTC).date().strftime("%Y%m%d")]
        events = self._fetch_events_for_dates(competition, request_dates)
        games = [self._parse_event(competition, event) for event in events]
        return [game for game in games if game]
