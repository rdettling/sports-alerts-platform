import pytest

from app.db.models import UserAlertPreference, UserGameAlertOverride
from app.services.alert_preferences import (
    AlertSettings,
    apply_sparse_overrides,
    default_alert_settings,
    resolve_alert_settings,
)


def test_canonical_alert_settings():
    assert default_alert_settings("NBA", "close_game_late") == AlertSettings(
        is_enabled=True,
        close_game_margin_threshold=5,
        close_game_time_threshold_seconds=300,
    )
    assert default_alert_settings("NFL", "close_game_late").close_game_margin_threshold == 8
    assert default_alert_settings("MLB", "inning_start").inning_start_threshold == 7
    assert default_alert_settings("MLS", "penalty_kicks") == AlertSettings(is_enabled=True)


def test_unsupported_alert_type_is_rejected():
    with pytest.raises(ValueError, match="Unsupported alert type"):
        default_alert_settings("NBA", "score_changed")


def test_preference_and_game_override_precedence():
    preference = UserAlertPreference(
        user_id=1,
        league="NBA",
        alert_type="close_game_late",
        is_enabled_override=False,
        close_game_margin_threshold_override=3,
    )
    game_override = UserGameAlertOverride(
        user_id=1,
        game_id=1,
        alert_type="close_game_late",
        is_enabled_override=True,
        close_game_time_threshold_seconds_override=60,
    )

    assert resolve_alert_settings("NBA", "close_game_late", preference, game_override) == AlertSettings(
        is_enabled=True,
        close_game_margin_threshold=3,
        close_game_time_threshold_seconds=60,
    )


def test_sparse_overrides_store_only_values_different_from_baseline():
    settings = AlertSettings(
        is_enabled=False,
        close_game_margin_threshold=5,
        close_game_time_threshold_seconds=90,
    )
    preference = UserAlertPreference(
        user_id=1,
        league="NBA",
        alert_type="close_game_late",
    )
    assert (
        apply_sparse_overrides(
            preference, settings, default_alert_settings("NBA", "close_game_late")
        )
        is True
    )
    assert preference.is_enabled_override is False
    assert preference.close_game_margin_threshold_override is None
    assert preference.close_game_time_threshold_seconds_override == 90
    assert preference.inning_start_threshold_override is None


def test_sparse_overrides_remove_values_equal_to_league_settings():
    game_override = UserGameAlertOverride(
        user_id=1, game_id=1, alert_type="close_game_late"
    )
    league_settings = AlertSettings(
        is_enabled=False,
        close_game_margin_threshold=3,
        close_game_time_threshold_seconds=90,
    )
    game_settings = AlertSettings(
        is_enabled=True,
        close_game_margin_threshold=3,
        close_game_time_threshold_seconds=60,
    )

    assert apply_sparse_overrides(game_override, game_settings, league_settings) is True
    assert game_override.is_enabled_override is True
    assert game_override.close_game_margin_threshold_override is None
    assert game_override.close_game_time_threshold_seconds_override == 60
