from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import (
    Alert,
    AlertDelivery,
    Game,
    Team,
    User,
    UserAlertPreference,
    UserGameFollow,
)
from app.services.competitions import competition_teams_query
from app.worker.ingest import run_catalog_sync, run_live_sync
from app.worker.period_events import classify_period_start
from app.worker.scoreboard import ScoreboardGame
from ingest_support import StaticProvider


@pytest.mark.parametrize(
    "competition,alert_type,period",
    [
        ("NBA", "quarter_start", 2),
        ("WNBA", "quarter_start", 4),
        ("NFL", "quarter_start", 3),
        ("FBS", "quarter_start", 4),
        ("NCAAB", "second_half_start", 2),
        ("NHL", "period_start", 3),
    ],
)
def test_period_start_transition(competition, alert_type, period):
    now = datetime.now(timezone.utc)
    previous = Game(
        competition=competition,
        status="in_progress",
        period=period - 1,
        clock="0:00",
        is_final=False,
        last_ingested_at=now,
    )
    payload = ScoreboardGame(
        "game", "1", "2", now, "in_progress", period=period, clock="14:45"
    )
    event = classify_period_start(previous, payload)
    assert event is not None
    assert event.alert_type == alert_type
    assert event.previous_observed_at == now


@pytest.mark.parametrize(
    "previous_period,previous_clock,period,clock,expected",
    [
        (1, "0:00", 2, "Halftime", False),
        (2, "Halftime", 2, "15:00", True),
        (2, "End of 1st", 2, "14:55", True),
        (2, "14:55", 2, "14:00", False),
        (2, None, 2, "14:00", False),
        (2, "0:00", 3, "0:00", False),
        (1, "0:00", 4, "14:00", False),
        (4, "0:00", 5, "10:00", False),
        (3, "14:00", 2, "14:00", False),
        (0, None, 1, "15:00", False),
    ],
)
def test_period_start_excludes_breaks_repeats_and_catchup(
    previous_period, previous_clock, period, clock, expected
):
    now = datetime.now(timezone.utc)
    previous = Game(
        competition="NFL",
        status="in_progress",
        period=previous_period,
        clock=previous_clock,
        is_final=False,
        last_ingested_at=now,
    )
    payload = ScoreboardGame(
        "game", "1", "2", now, "in_progress", period=period, clock=clock
    )
    assert (classify_period_start(previous, payload) is not None) is expected


@pytest.mark.parametrize("competition,period", [("NCAAB", 3), ("NHL", 4)])
def test_period_start_excludes_overtime_and_other_sports(competition, period):
    now = datetime.now(timezone.utc)
    previous = Game(
        competition=competition,
        status="in_progress",
        period=period - 1,
        clock="0:00",
        is_final=False,
        last_ingested_at=now,
    )
    payload = ScoreboardGame(
        "game", "1", "2", now, "in_progress", period=period, clock="14:45"
    )
    assert classify_period_start(previous, payload) is None


@pytest.mark.parametrize(
    "status,is_final", [("scheduled", False), ("final", True), ("postponed", False)]
)
def test_period_start_requires_live_game(status, is_final):
    now = datetime.now(timezone.utc)
    previous = Game(
        competition="NBA",
        status=status,
        period=1,
        clock="0:00",
        is_final=is_final,
        last_ingested_at=now,
    )
    payload = ScoreboardGame(
        "game", "1", "2", now, "in_progress", period=2, clock="11:45"
    )
    assert classify_period_start(previous, payload) is None
    previous.status, previous.is_final = "in_progress", False
    payload.status, payload.is_final = status, is_final
    assert classify_period_start(previous, payload) is None


@pytest.mark.parametrize(
    "competition,alert_type",
    [
        ("NBA", "quarter_start"),
        ("WNBA", "quarter_start"),
        ("NFL", "quarter_start"),
        ("FBS", "quarter_start"),
        ("NCAAB", "second_half_start"),
        ("NHL", "period_start"),
        ("MLS", "second_half_start"),
        ("CHAMPIONS_LEAGUE", "second_half_start"),
    ],
)
@pytest.mark.parametrize("sync", [run_catalog_sync, run_live_sync])
def test_ingest_period_starts_are_opt_in_and_deduped(
    db_session, competition, alert_type, sync
):
    teams = db_session.scalars(
        competition_teams_query(competition).order_by(Team.id).limit(2)
    ).all()
    now = datetime.now(timezone.utc)
    payload = ScoreboardGame(
        "period-start",
        teams[0].external_team_id,
        teams[1].external_team_id,
        now - timedelta(hours=1),
        "in_progress",
        period=1,
        clock="0:00",
        home_score=10,
        away_score=7,
    )
    provider = StaticProvider([payload])
    run_catalog_sync(provider, competition)
    game = db_session.scalar(
        select(Game).where(Game.external_game_id == "period-start")
    )
    users = [
        User(email=f"{role}@example.com") for role in ("enabled", "default", "late")
    ]
    db_session.add_all(users)
    db_session.flush()
    for user in users:
        db_session.add(
            UserGameFollow(
                user_id=user.id, game_id=game.id, created_at=now - timedelta(hours=2)
            )
        )
    db_session.add(
        UserAlertPreference(
            user_id=users[0].id,
            competition=competition,
            alert_type=alert_type,
            is_enabled_override=True,
        )
    )
    db_session.add(
        UserAlertPreference(
            user_id=users[2].id,
            competition=competition,
            alert_type=alert_type,
            is_enabled_override=True,
        )
    )
    db_session.commit()

    payload.period, payload.clock = 2, "Halftime"
    sync(provider, competition)
    assert (
        db_session.scalars(select(Alert).where(Alert.alert_type == alert_type)).all()
        == []
    )
    # This follower arrived after the last observation; don't send a catch-up start.
    late_follow = db_session.scalar(
        select(UserGameFollow).where(UserGameFollow.user_id == users[2].id)
    )
    late_follow.created_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.commit()
    payload.clock = "46'" if competition in {"MLS", "CHAMPIONS_LEAGUE"} else "11:45"
    sync(provider, competition)
    sync(provider, competition)
    payload.clock = "48'" if competition in {"MLS", "CHAMPIONS_LEAGUE"} else "10:45"
    sync(provider, competition)
    # A feed correction must not notify a second time for the same period.
    payload.period, payload.clock = 1, "0:00"
    sync(provider, competition)
    payload.period = 2
    payload.clock = "46'" if competition in {"MLS", "CHAMPIONS_LEAGUE"} else "11:45"
    sync(provider, competition)

    alerts = db_session.scalars(
        select(Alert).where(Alert.alert_type == alert_type)
    ).all()
    assert len(alerts) == 1
    assert alerts[0].user_id == users[0].id
    assert alerts[0].event_data["period"] == 2
    deliveries = db_session.scalars(
        select(AlertDelivery).where(AlertDelivery.alert_id == alerts[0].id)
    ).all()
    assert [(delivery.channel, delivery.status) for delivery in deliveries] == [
        ("email", "pending")
    ]


@pytest.mark.parametrize(
    "competition", ["MLS", "LA_LIGA", "PREMIER_LEAGUE", "CHAMPIONS_LEAGUE"]
)
@pytest.mark.parametrize(
    "previous_period,previous_clock,period,clock,alert_type",
    [
        (1, "45+2'", 2, "HT", None),
        (2, "HT", 2, "46'", "second_half_start"),
        (1, "45+2'", 2, "46'", "second_half_start"),
        (2, "46'", 2, "48'", None),
        (2, "90+5'", 2, "ET", None),
        (2, "90+5'", 3, "91'", "extra_time_start"),
        (3, "105'", 4, "106'", None),
        (4, "120'", 5, "Pens", None),
    ],
)
def test_soccer_uses_shared_period_classifier(
    competition, previous_period, previous_clock, period, clock, alert_type
):
    now = datetime.now(timezone.utc)
    previous = Game(
        competition=competition,
        status="in_progress",
        period=previous_period,
        clock=previous_clock,
        is_final=False,
        last_ingested_at=now,
    )
    payload = ScoreboardGame(
        "game", "1", "2", now, "in_progress", period=period, clock=clock
    )
    event = classify_period_start(previous, payload)
    assert (event.alert_type if event else None) == alert_type


@pytest.mark.parametrize(
    "alert_type,period,event_key",
    [
        ("second_half_start", 2, "second_half_start"),
        ("extra_time_start", 3, "extra_time_start"),
        ("quarter_start", 3, "quarter_start:3"),
        ("period_start", 2, "period_start:2"),
    ],
)
def test_shared_period_rules_preserve_event_keys_and_follow_cutoff(
    alert_type, period, event_key
):
    from app.services.alert_preferences import AlertSettings
    from app.worker.alert_rules import detect_alerts
    from app.worker.period_events import PeriodStartEvent

    now = datetime.now(timezone.utc)
    game = Game(
        competition="MLS",
        status="in_progress",
        period=period,
        clock="46'",
        is_final=False,
        home_score=0,
        away_score=0,
    )
    event = PeriodStartEvent(alert_type, now)
    settings = {alert_type: AlertSettings(is_enabled=True, periods=[2, 3, 4] if alert_type == "quarter_start" else [2, 3] if alert_type == "period_start" else None)}
    alerts = detect_alerts(
        game, now - timedelta(seconds=1), settings, period_start=event
    )
    assert [(alert.alert_type, alert.event_key_suffix) for alert in alerts] == [
        (alert_type, event_key)
    ]
    assert (
        detect_alerts(game, now + timedelta(seconds=1), settings, period_start=event)
        == []
    )
    assert (
        detect_alerts(
            game, now, {alert_type: AlertSettings(is_enabled=False)}, period_start=event
        )
        == []
    )


@pytest.mark.parametrize("competition,alert_type,options,periods", [
    ("NBA", "quarter_start", [2, 3, 4], periods)
    for periods in [[], [2], [3], [4], [2, 3], [2, 4], [3, 4], [2, 3, 4]]
] + [
    ("NHL", "period_start", [2, 3], periods)
    for periods in [[], [2], [3], [2, 3]]
])
def test_starts_only_notify_selected_periods(competition, alert_type, options, periods):
    from app.services.alert_preferences import AlertSettings
    from app.worker.alert_rules import detect_alerts
    from app.worker.period_events import PeriodStartEvent

    now = datetime.now(timezone.utc)
    settings = {alert_type: AlertSettings(is_enabled=True, periods=periods)}
    for period in options:
        game = Game(competition=competition, status="in_progress", period=period, clock="11:55", is_final=False)
        alerts = detect_alerts(game, now - timedelta(seconds=1), settings,
                               period_start=PeriodStartEvent(alert_type, now))
        assert bool(alerts) == (period in periods)


@pytest.mark.parametrize("inning", range(1, 10))
def test_each_regulation_inning_can_start(inning):
    now = datetime.now(timezone.utc)
    previous = Game(competition="MLB", status="scheduled" if inning == 1 else "in_progress",
                    period=inning - 1, clock=f"End {inning - 1}", is_final=False, last_ingested_at=now)
    payload = ScoreboardGame("game", "1", "2", now, "in_progress", period=inning, clock=f"Top {inning}")
    event = classify_period_start(previous, payload)
    assert event is not None and event.alert_type == "inning_start"


@pytest.mark.parametrize("clock", ["Bot 7th", "Mid 7th", "End 7th", "Rain Delay", None])
def test_inning_start_waits_for_top_of_inning(clock):
    now = datetime.now(timezone.utc)
    previous = Game(competition="MLB", status="in_progress", period=6, clock="End 6th",
                    is_final=False, last_ingested_at=now)
    payload = ScoreboardGame("game", "1", "2", now, "in_progress", period=7, clock=clock)
    assert classify_period_start(previous, payload) is None


def test_selected_innings_deliver_once_per_inning(db_session):
    teams = db_session.scalars(competition_teams_query("MLB").order_by(Team.id).limit(2)).all()
    now = datetime.now(timezone.utc)
    user = User(email="selected-innings@example.com")
    db_session.add(user)
    db_session.commit()
    payload = ScoreboardGame("selected-innings", teams[0].external_team_id, teams[1].external_team_id,
                            now - timedelta(hours=1), "scheduled", period=0)
    provider = StaticProvider([payload])
    run_catalog_sync(provider, "MLB")
    game = db_session.scalar(select(Game).where(Game.external_game_id == payload.external_game_id))
    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id, created_at=now - timedelta(hours=2)))
    db_session.add(UserAlertPreference(user_id=user.id, competition="MLB", alert_type="inning_start",
                                     is_enabled_override=True, periods_override=[1, 5, 9]))
    db_session.commit()
    for inning in range(1, 11):
        for clock in (f"Top {inning}", f"Top {inning}", f"Bot {inning}", f"End {inning}"):
            payload.period, payload.clock, payload.status = inning, clock, "in_progress"
            run_catalog_sync(provider, "MLB")
    alerts = db_session.scalars(select(Alert).where(Alert.alert_type == "inning_start").order_by(Alert.id)).all()
    assert [alert.event_data["period"] for alert in alerts] == [1, 5, 9]
    assert [alert.event_key.rsplit(":", 2)[-2:] for alert in alerts] == [["inning_start", "1"], ["inning_start", "5"], ["inning_start", "9"]]
