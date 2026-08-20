from __future__ import annotations

from dataclasses import dataclass

from app.db.models import UserAlertPreference, UserGameAlertOverride
from app.services.competitions import get_sport_alert_types, normalize_sport


@dataclass(frozen=True)
class AlertSettings:
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None


def default_alert_settings(sport: str, alert_type: str) -> AlertSettings:
    normalized_sport = normalize_sport(sport)
    if alert_type not in get_sport_alert_types(normalized_sport):
        raise ValueError(f"Unsupported alert type for {normalized_sport}: {alert_type}")
    if alert_type == "close_game_late":
        return AlertSettings(
            is_enabled=True,
            close_game_margin_threshold=8 if normalized_sport == "football" else 5,
            close_game_time_threshold_seconds=300,
        )
    if alert_type == "inning_start":
        return AlertSettings(is_enabled=True, inning_start_threshold=7)
    return AlertSettings(is_enabled=True)


def resolve_alert_settings(
    sport: str,
    alert_type: str,
    preference: UserAlertPreference | None = None,
    game_override: UserGameAlertOverride | None = None,
) -> AlertSettings:
    defaults = default_alert_settings(sport, alert_type)
    return AlertSettings(
        is_enabled=_resolve_value(
            defaults.is_enabled,
            preference.is_enabled_override if preference else None,
            game_override.is_enabled_override if game_override else None,
        ),
        close_game_margin_threshold=_resolve_value(
            defaults.close_game_margin_threshold,
            preference.close_game_margin_threshold_override if preference else None,
            game_override.close_game_margin_threshold_override
            if game_override
            else None,
        ),
        close_game_time_threshold_seconds=_resolve_value(
            defaults.close_game_time_threshold_seconds,
            preference.close_game_time_threshold_seconds_override
            if preference
            else None,
            game_override.close_game_time_threshold_seconds_override
            if game_override
            else None,
        ),
        inning_start_threshold=_resolve_value(
            defaults.inning_start_threshold,
            preference.inning_start_threshold_override if preference else None,
            game_override.inning_start_threshold_override if game_override else None,
        ),
    )


def apply_sparse_overrides(
    row: UserAlertPreference | UserGameAlertOverride,
    settings: AlertSettings,
    baseline: AlertSettings,
) -> bool:
    values = {
        "is_enabled_override": _override_value(
            settings.is_enabled, baseline.is_enabled
        ),
        "close_game_margin_threshold_override": _override_value(
            settings.close_game_margin_threshold,
            baseline.close_game_margin_threshold,
        ),
        "close_game_time_threshold_seconds_override": _override_value(
            settings.close_game_time_threshold_seconds,
            baseline.close_game_time_threshold_seconds,
        ),
        "inning_start_threshold_override": _override_value(
            settings.inning_start_threshold,
            baseline.inning_start_threshold,
        ),
    }
    for name, value in values.items():
        setattr(row, name, value)
    return any(value is not None for value in values.values())


def _resolve_value(default, preference_override, game_override):
    if game_override is not None:
        return game_override
    if preference_override is not None:
        return preference_override
    return default


def _override_value(value, default):
    return None if value is None or value == default else value
