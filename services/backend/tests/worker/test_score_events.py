from datetime import datetime, timezone

import pytest

from app.db.models import Game
from app.services.alert_preferences import AlertSettings
from app.worker.alert_rules import detect_alerts
from app.worker.score_events import classify_score_change

from ingest_support import make_game


def _stored_game(
    home_score: int,
    away_score: int,
    *,
    period: int = 3,
    clock: str = "08:00",
) -> Game:
    return Game(
        external_game_id="football-score-event",
        competition="FBS",
        home_team_id=1,
        away_team_id=2,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=home_score,
        away_score=away_score,
        period=period,
        clock=clock,
    )


def _payload(
    home_score: int | None,
    away_score: int | None,
    *,
    status: str = "in_progress",
    is_final: bool = False,
    period: int = 3,
    clock: str = "07:15",
):
    return make_game(
        external_game_id="football-score-event",
        home_external_team_id="660",
        away_external_team_id="203",
        status=status,
        home_score=home_score,
        away_score=away_score,
        period=period,
        clock=clock,
        is_final=is_final,
    )


@pytest.mark.parametrize(
    ("previous", "updated", "previous_leader", "new_leader", "lead_changed"),
    [
        ((0, 0), (7, 0), "tied", "home", False),
        ((14, 7), (14, 14), "home", "tied", True),
        ((14, 14), (17, 14), "tied", "home", True),
        ((14, 17), (21, 17), "away", "home", True),
        ((14, 17), (14, 24), "away", "away", False),
    ],
)
def test_football_score_change_classifies_lead_transitions(
    previous,
    updated,
    previous_leader,
    new_leader,
    lead_changed,
):
    event = classify_score_change(
        _stored_game(*previous),
        _payload(*updated),
        sport="football",
    )

    assert event is not None
    assert event.previous_leader == previous_leader
    assert event.new_leader == new_leader
    assert event.lead_changed is lead_changed


def test_football_score_change_preserves_aggregate_update_metadata():
    event = classify_score_change(
        _stored_game(7, 10),
        _payload(14, 17),
        sport="football",
    )

    assert event is not None
    assert event.scoring_side is None
    assert event.is_inferred_goal is False
    assert (event.previous_home_score, event.previous_away_score) == (7, 10)
    assert (event.new_home_score, event.new_away_score) == (14, 17)
    assert (event.period, event.clock, event.status) == (3, "07:15", "in_progress")


@pytest.mark.parametrize(
    "payload",
    [
        _payload(14, 10),
        _payload(13, 10),
        _payload(None, 10),
        _payload(17, 10, status="final", is_final=True),
    ],
)
def test_football_score_change_ignores_non_events(payload):
    assert classify_score_change(_stored_game(14, 10), payload, sport="football") is None


def _hockey_game(
    home_score: int,
    away_score: int,
    *,
    period: int = 3,
    clock: str = "04:30",
) -> Game:
    game = _stored_game(home_score, away_score, period=period, clock=clock)
    game.competition = "NHL"
    return game


def test_hockey_score_change_classifies_goals_and_ignores_shootouts():
    goal = classify_score_change(
        _hockey_game(1, 1),
        _payload(2, 1, period=3, clock="04:30"),
        sport="hockey",
    )

    assert goal is not None
    assert goal.is_inferred_goal is True
    assert goal.scoring_side == "home"
    assert (
        classify_score_change(
            _hockey_game(3, 3, period=5),
            _payload(4, 3, period=5),
            sport="hockey",
        )
        is None
    )


@pytest.mark.parametrize(
    ("period", "clock", "home_score", "away_score", "expected"),
    [
        (3, "05:00", 2, 1, ["close_game_late"]),
        (3, "04:59", 3, 1, []),
        (2, "01:00", 2, 1, []),
        (4, "04:00", 2, 1, []),
    ],
)
def test_hockey_close_game_only_triggers_in_the_final_five_minutes_of_period_three(
    period,
    clock,
    home_score,
    away_score,
    expected,
):
    detected = detect_alerts(
        _hockey_game(home_score, away_score, period=period, clock=clock),
        None,
        {
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=1,
                close_game_time_threshold_seconds=300,
            )
        },
    )

    assert [alert.alert_type for alert in detected] == expected


@pytest.mark.parametrize("score_enabled", [True, False])
def test_hockey_goal_takes_precedence_over_close_game_when_enabled(score_enabled):
    game = _hockey_game(2, 1)
    event = classify_score_change(
        _hockey_game(1, 1),
        _payload(2, 1, period=3, clock="04:30"),
        sport="hockey",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "score_changed": AlertSettings(is_enabled=score_enabled),
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=1,
                close_game_time_threshold_seconds=300,
            ),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == [
        "score_changed" if score_enabled else "close_game_late"
    ]
    if score_enabled:
        assert detected[0].event_data["covers_close_game_late"] is True


def test_ambiguous_hockey_score_change_remains_separate_from_close_game():
    event = classify_score_change(
        _hockey_game(1, 1),
        _payload(3, 2, period=3, clock="04:30"),
        sport="hockey",
    )
    assert event is not None
    assert event.is_inferred_goal is False

    detected = detect_alerts(
        _hockey_game(3, 2),
        None,
        {
            "score_changed": AlertSettings(is_enabled=True),
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=1,
                close_game_time_threshold_seconds=300,
            ),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == ["score_changed", "close_game_late"]
    assert "covers_close_game_late" not in detected[0].event_data


def test_hockey_overtime_uses_one_event_key_through_shootout():
    settings = {"overtime_start": AlertSettings(is_enabled=True)}

    overtime = detect_alerts(_hockey_game(2, 2, period=4), None, settings)
    shootout = detect_alerts(_hockey_game(2, 2, period=5), None, settings)

    assert [alert.event_key_suffix for alert in overtime] == ["overtime_start"]
    assert [alert.event_key_suffix for alert in shootout] == ["overtime_start"]


@pytest.mark.parametrize(
    ("score_enabled", "lead_enabled", "expected"),
    [
        (False, False, []),
        (True, False, ["score_changed"]),
        (False, True, ["lead_change"]),
        (True, True, ["lead_change"]),
    ],
)
def test_lead_change_takes_precedence_over_score_update(score_enabled, lead_enabled, expected):
    game = _stored_game(21, 17)
    event = classify_score_change(
        _stored_game(14, 17),
        _payload(21, 17),
        sport="football",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "score_changed": AlertSettings(is_enabled=score_enabled),
            "lead_change": AlertSettings(is_enabled=lead_enabled),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == expected


def test_lead_extension_remains_a_score_update_when_both_are_enabled():
    game = _stored_game(14, 24)
    event = classify_score_change(
        _stored_game(14, 17),
        _payload(14, 24),
        sport="football",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "score_changed": AlertSettings(is_enabled=True),
            "lead_change": AlertSettings(is_enabled=True),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == ["score_changed"]


@pytest.mark.parametrize(
    ("lead_enabled", "close_enabled", "score_enabled", "expected", "covers_close"),
    [
        (False, False, False, [], False),
        (False, False, True, ["score_changed"], False),
        (False, True, False, ["close_game_late"], False),
        (False, True, True, ["close_game_late"], False),
        (True, False, False, ["lead_change"], False),
        (True, False, True, ["lead_change"], False),
        (True, True, False, ["lead_change"], True),
        (True, True, True, ["lead_change"], True),
    ],
)
def test_football_scoring_alert_priority_in_close_game_window(
    lead_enabled,
    close_enabled,
    score_enabled,
    expected,
    covers_close,
):
    game = _stored_game(24, 21, period=4, clock="03:00")
    event = classify_score_change(
        _stored_game(17, 21, period=4, clock="06:00"),
        _payload(24, 21, period=4, clock="03:00"),
        sport="football",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "lead_change": AlertSettings(is_enabled=lead_enabled),
            "close_game_late": AlertSettings(
                is_enabled=close_enabled,
                close_game_margin_threshold=8,
                close_game_time_threshold_seconds=300,
            ),
            "score_changed": AlertSettings(is_enabled=score_enabled),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == expected
    if detected:
        assert bool(detected[0].event_data.get("covers_close_game_late")) is covers_close


def test_close_game_beats_non_lead_score_update_and_keeps_event_metadata():
    game = _stored_game(20, 13, period=4, clock="03:00")
    event = classify_score_change(
        _stored_game(20, 10, period=4, clock="05:00"),
        _payload(20, 13, period=4, clock="03:00"),
        sport="football",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=8,
                close_game_time_threshold_seconds=300,
            ),
            "score_changed": AlertSettings(is_enabled=True),
        },
        event,
    )

    assert [alert.alert_type for alert in detected] == ["close_game_late"]
    assert detected[0].event_key_suffix == "close_game_late"
    assert detected[0].event_data["previous_away_score"] == 10
    assert detected[0].event_data["new_away_score"] == 13
    assert detected[0].event_data["clock"] == "03:00"


@pytest.mark.parametrize(
    ("lead_enabled", "expected"),
    [
        (False, ["score_changed"]),
        (True, ["lead_change"]),
    ],
)
def test_existing_close_notification_does_not_suppress_later_scoring_alerts(
    lead_enabled,
    expected,
):
    game = _stored_game(24, 21, period=4, clock="02:00")
    event = classify_score_change(
        _stored_game(17, 21, period=4, clock="03:00"),
        _payload(24, 21, period=4, clock="02:00"),
        sport="football",
    )
    assert event is not None

    detected = detect_alerts(
        game,
        None,
        {
            "lead_change": AlertSettings(is_enabled=lead_enabled),
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=8,
                close_game_time_threshold_seconds=300,
            ),
            "score_changed": AlertSettings(is_enabled=True),
        },
        event,
        close_game_already_notified=True,
    )

    assert [alert.alert_type for alert in detected] == expected
    assert "covers_close_game_late" not in detected[0].event_data


def test_close_game_still_triggers_without_a_score_change():
    detected = detect_alerts(
        _stored_game(20, 13, period=4, clock="03:00"),
        None,
        {
            "close_game_late": AlertSettings(
                is_enabled=True,
                close_game_margin_threshold=8,
                close_game_time_threshold_seconds=300,
            )
        },
    )

    assert [alert.alert_type for alert in detected] == ["close_game_late"]
