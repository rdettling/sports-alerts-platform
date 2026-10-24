import pytest

from app.db.models import Game
from app.services.alert_preferences import AlertSettings
from app.worker.alert_rules import detect_alerts


@pytest.mark.parametrize("period,expected", [
    (1, set()),
    (2, {"close_game_late"}),
    (3, {"close_game_late", "overtime_start"}),
    (4, {"close_game_late", "overtime_start"}),
])
def test_two_half_basketball_alerts(period, expected):
    game = Game(
        competition="NCAAB", status="in_progress", is_final=False,
        home_score=70, away_score=69, period=period, clock="01:00",
    )
    settings = {
        "close_game_late": AlertSettings(is_enabled=True),
        "overtime_start": AlertSettings(is_enabled=True),
    }
    alerts = detect_alerts(game, None, settings)
    assert {alert.alert_type for alert in alerts} == expected
    overtime = next((alert for alert in alerts if alert.alert_type == "overtime_start"), None)
    if overtime:
        assert overtime.event_key_suffix == f"overtime_start:{period}"
