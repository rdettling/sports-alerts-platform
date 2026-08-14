from __future__ import annotations

from dataclasses import dataclass

from app.services.leagues import get_league_profile


@dataclass(frozen=True)
class AlertDefaultValues:
    is_enabled: bool
    close_game_margin_threshold: int | None
    close_game_time_threshold_seconds: int | None
    inning_start_threshold: int | None


_ALERT_DEFAULTS: dict[str, AlertDefaultValues] = {
    "game_start": AlertDefaultValues(
        is_enabled=True,
        close_game_margin_threshold=None,
        close_game_time_threshold_seconds=None,
        inning_start_threshold=None,
    ),
    "close_game_late": AlertDefaultValues(
        is_enabled=True,
        close_game_margin_threshold=5,
        close_game_time_threshold_seconds=300,
        inning_start_threshold=None,
    ),
    "inning_start": AlertDefaultValues(
        is_enabled=True,
        close_game_margin_threshold=None,
        close_game_time_threshold_seconds=None,
        inning_start_threshold=7,
    ),
    "final_result": AlertDefaultValues(
        is_enabled=True,
        close_game_margin_threshold=None,
        close_game_time_threshold_seconds=None,
        inning_start_threshold=None,
    ),
}


def get_alert_default_values(league: str, alert_type: str) -> AlertDefaultValues:
    defaults = _ALERT_DEFAULTS.get(
        alert_type,
        AlertDefaultValues(
            is_enabled=True,
            close_game_margin_threshold=None,
            close_game_time_threshold_seconds=None,
            inning_start_threshold=None,
        ),
    )
    if alert_type == "close_game_late" and get_league_profile(league).sport == "football":
        return AlertDefaultValues(
            is_enabled=defaults.is_enabled,
            close_game_margin_threshold=8,
            close_game_time_threshold_seconds=300,
            inning_start_threshold=None,
        )
    return defaults
