from __future__ import annotations

from dataclasses import dataclass

from app.db.models import UserAlertPreference, UserGameAlertOverride
from app.services.competitions import get_alert_types, get_competition_profile


@dataclass(frozen=True)
class AlertSettings:
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    periods: list[int] | None = None


def default_alert_settings(competition: str, alert_type: str) -> AlertSettings:
    sport = get_competition_profile(competition).sport
    if alert_type not in get_alert_types(competition):
        raise ValueError(f"Unsupported alert type for {competition}: {alert_type}")
    if alert_type == "close_game_late":
        margin = {"football": 8, "hockey": 1}.get(sport, 5)
        return AlertSettings(
            is_enabled=True,
            close_game_margin_threshold=margin,
            close_game_time_threshold_seconds=300,
        )
    if alert_type == "quarter_start":
        return AlertSettings(is_enabled=False, periods=[2, 3, 4])
    if alert_type == "period_start":
        return AlertSettings(is_enabled=False, periods=[2, 3])
    if alert_type == "inning_start":
        return AlertSettings(is_enabled=False, periods=[7])
    if alert_type in {"score_changed", "lead_change", "second_half_start"}:
        return AlertSettings(is_enabled=False)
    return AlertSettings(is_enabled=True)


def resolve_alert_settings(
    competition: str,
    alert_type: str,
    preference: UserAlertPreference | None = None,
    game_override: UserGameAlertOverride | None = None,
) -> AlertSettings:
    defaults = default_alert_settings(competition, alert_type)
    return AlertSettings(
        periods=_resolve_value(
            defaults.periods,
            preference.periods_override if preference else None,
            game_override.periods_override if game_override else None,
        ),
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
    )


def apply_sparse_overrides(
    row: UserAlertPreference | UserGameAlertOverride,
    settings: AlertSettings,
    baseline: AlertSettings,
) -> bool:
    values = {
        "periods_override": _override_value(settings.periods, baseline.periods),
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
