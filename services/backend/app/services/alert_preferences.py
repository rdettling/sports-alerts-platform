from __future__ import annotations

from dataclasses import dataclass

from app.db.models import UserAlertPreference, UserGameAlertOverride
from app.services.leagues import get_alert_types, get_league_profile, normalize_league


@dataclass(frozen=True)
class AlertSettings:
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None


def default_alert_settings(league: str, alert_type: str) -> AlertSettings:
    normalized_league = normalize_league(league)
    if alert_type not in get_alert_types(normalized_league):
        raise ValueError(f"Unsupported alert type for {normalized_league}: {alert_type}")
    if alert_type == "close_game_late":
        return AlertSettings(
            is_enabled=True,
            close_game_margin_threshold=8 if get_league_profile(normalized_league).sport == "football" else 5,
            close_game_time_threshold_seconds=300,
        )
    if alert_type == "inning_start":
        return AlertSettings(is_enabled=True, inning_start_threshold=7)
    return AlertSettings(is_enabled=True)


def resolve_alert_settings(
    league: str,
    alert_type: str,
    preference: UserAlertPreference | None = None,
    game_override: UserGameAlertOverride | None = None,
) -> AlertSettings:
    defaults = default_alert_settings(league, alert_type)
    return AlertSettings(
        is_enabled=_resolve_value(
            defaults.is_enabled,
            preference.is_enabled_override if preference else None,
            game_override.is_enabled_override if game_override else None,
        ),
        close_game_margin_threshold=_resolve_value(
            defaults.close_game_margin_threshold,
            preference.close_game_margin_threshold_override if preference else None,
            game_override.close_game_margin_threshold_override if game_override else None,
        ),
        close_game_time_threshold_seconds=_resolve_value(
            defaults.close_game_time_threshold_seconds,
            preference.close_game_time_threshold_seconds_override if preference else None,
            game_override.close_game_time_threshold_seconds_override if game_override else None,
        ),
        inning_start_threshold=_resolve_value(
            defaults.inning_start_threshold,
            preference.inning_start_threshold_override if preference else None,
            game_override.inning_start_threshold_override if game_override else None,
        ),
    )


def preference_override_values(league: str, alert_type: str, settings: AlertSettings) -> dict[str, bool | int | None]:
    defaults = default_alert_settings(league, alert_type)
    return {
        "is_enabled_override": _override_value(settings.is_enabled, defaults.is_enabled),
        "close_game_margin_threshold_override": _override_value(
            settings.close_game_margin_threshold,
            defaults.close_game_margin_threshold,
        ),
        "close_game_time_threshold_seconds_override": _override_value(
            settings.close_game_time_threshold_seconds,
            defaults.close_game_time_threshold_seconds,
        ),
        "inning_start_threshold_override": _override_value(
            settings.inning_start_threshold,
            defaults.inning_start_threshold,
        ),
    }


def compact_game_override(
    override: UserGameAlertOverride,
    league_settings: AlertSettings,
) -> bool:
    override.is_enabled_override = _override_value(override.is_enabled_override, league_settings.is_enabled)
    override.close_game_margin_threshold_override = _override_value(
        override.close_game_margin_threshold_override,
        league_settings.close_game_margin_threshold,
    )
    override.close_game_time_threshold_seconds_override = _override_value(
        override.close_game_time_threshold_seconds_override,
        league_settings.close_game_time_threshold_seconds,
    )
    override.inning_start_threshold_override = _override_value(
        override.inning_start_threshold_override,
        league_settings.inning_start_threshold,
    )
    return any(
        value is not None
        for value in (
            override.is_enabled_override,
            override.close_game_margin_threshold_override,
            override.close_game_time_threshold_seconds_override,
            override.inning_start_threshold_override,
        )
    )


def _resolve_value(default, preference_override, game_override):
    if game_override is not None:
        return game_override
    if preference_override is not None:
        return preference_override
    return default


def _override_value(value, default):
    return None if value is None or value == default else value
