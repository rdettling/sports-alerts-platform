from __future__ import annotations

from dataclasses import dataclass


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


def get_alert_default_values(alert_type: str) -> AlertDefaultValues:
    return _ALERT_DEFAULTS.get(
        alert_type,
        AlertDefaultValues(
            is_enabled=True,
            close_game_margin_threshold=None,
            close_game_time_threshold_seconds=None,
            inning_start_threshold=None,
        ),
    )
