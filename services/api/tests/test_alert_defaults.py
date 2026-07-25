from app.services.alert_defaults import get_alert_default_values


def test_close_game_late_defaults():
    defaults = get_alert_default_values("close_game_late")
    assert defaults.is_enabled is True
    assert defaults.close_game_margin_threshold == 5
    assert defaults.close_game_time_threshold_seconds == 300
    assert defaults.inning_start_threshold is None


def test_inning_start_defaults():
    defaults = get_alert_default_values("inning_start")
    assert defaults.is_enabled is True
    assert defaults.close_game_margin_threshold is None
    assert defaults.close_game_time_threshold_seconds is None
    assert defaults.inning_start_threshold == 7


def test_other_alert_types_default_to_enabled_without_thresholds():
    for alert_type in ("game_start", "overtime_start", "final_result", "unknown-alert-type"):
        defaults = get_alert_default_values(alert_type)
        assert defaults.is_enabled is True
        assert defaults.close_game_margin_threshold is None
        assert defaults.close_game_time_threshold_seconds is None
        assert defaults.inning_start_threshold is None
