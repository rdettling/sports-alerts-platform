from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    Alert,
    AlertDelivery,
    Game,
    PushSubscription,
    Team,
    User,
    UserAlertPreference,
    UserGameAlertOverride,
    UserGameFollow,
    UserGameUnfollow,
    UserTeamFollow,
)
from app.services.competitions import competition_teams_query
from app.worker.ingest import run_catalog_sync
from app.worker.planner import build_live_requests

from ingest_support import (
    LongClockProvider,
    StaticProvider,
    make_final_provider,
    make_game,
    make_live_close_provider,
    make_mlb_inning_provider,
)


def test_ingest_uses_defaults_without_materializing_preferences(db_session):
    user = User(email="default-alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(competition_teams_query("NBA").order_by(Team.id.asc()))
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.commit()

    result = run_catalog_sync(make_live_close_provider())

    assert result.alerts_created == 2
    assert sorted(
        db_session.scalars(select(Alert.alert_type).where(Alert.user_id == user.id)).all()
    ) == ["close_game_late", "game_start"]
    assert db_session.scalars(
        select(UserAlertPreference).where(UserAlertPreference.user_id == user.id)
    ).all() == []


def test_ingest_creates_deduped_live_alerts(db_session):
    user = User(email="alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=True))
    db_session.add(
        UserAlertPreference(
            user_id=user.id,
            sport="basketball",
            alert_type="close_game_late",
            is_enabled_override=True,
            close_game_margin_threshold_override=5,
            close_game_time_threshold_seconds_override=120,
        )
    )
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
    run_catalog_sync(make_live_close_provider())

    sent = db_session.scalars(select(Alert).order_by(Alert.alert_type.asc())).all()
    assert len(sent) == 2
    assert sorted([row.alert_type for row in sent]) == ["close_game_late", "game_start"]
    assert all(row.deliveries[0].status == "sent" for row in sent)


def test_ingest_supports_every_email_and_push_combination(db_session):
    users = {
        "email": User(email="email-only@example.com"),
        "push": User(email="push-only@example.com", email_alerts_enabled=False),
        "both": User(email="both@example.com"),
        "neither": User(email="neither@example.com", email_alerts_enabled=False),
    }
    db_session.add_all(users.values())
    db_session.commit()
    for user in users.values():
        db_session.refresh(user)

    team = db_session.scalar(competition_teams_query("NBA").order_by(Team.id.asc()))
    assert team is not None
    for label, user in users.items():
        db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
        db_session.add(
            UserAlertPreference(
                user_id=user.id,
                sport="basketball",
                alert_type="game_start",
                is_enabled_override=True,
            )
        )
        if label in {"push", "both"}:
            db_session.add(
                PushSubscription(
                    user_id=user.id,
                    endpoint=f"https://push.example/{label}",
                    p256dh="p" * 43,
                    auth="a" * 22,
                )
            )
    db_session.commit()

    first = run_catalog_sync(make_live_close_provider())
    second = run_catalog_sync(make_live_close_provider())

    assert first.alerts_created >= 4
    assert second.alerts_created == 0
    expected_channels = {
        "email": ["email"],
        "push": ["push"],
        "both": ["email", "push"],
        "neither": [],
    }
    for label, user in users.items():
        alerts = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
        game_start = next(alert for alert in alerts if alert.alert_type == "game_start")
        assert [row.channel for row in game_start.deliveries] == expected_channels[label]
        assert all(row.status == "sent" for row in game_start.deliveries)


def test_nba_overtime_start_alerts_once_per_overtime_period(db_session):
    enabled_user = User(email="overtime@example.com")
    disabled_user = User(email="no-overtime@example.com")
    db_session.add_all([enabled_user, disabled_user])
    db_session.commit()
    db_session.refresh(enabled_user)
    db_session.refresh(disabled_user)

    team = db_session.scalar(competition_teams_query("NBA").where(Team.external_team_id == "1"))
    assert team is not None
    for user, overtime_enabled in ((enabled_user, True), (disabled_user, False)):
        db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
        db_session.add(
            UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=False)
        )
        db_session.add(
            UserAlertPreference(user_id=user.id, sport="basketball", alert_type="close_game_late", is_enabled_override=False)
        )
        db_session.add(
            UserAlertPreference(
                user_id=user.id,
                sport="basketball",
                alert_type="overtime_start",
                is_enabled_override=overtime_enabled,
            )
        )
    db_session.commit()

    def overtime_provider(period: int, *, status: str = "in_progress", is_final: bool = False) -> StaticProvider:
        return StaticProvider(
            [
                make_game(
                    external_game_id="game-overtime",
                    home_external_team_id="1",
                    away_external_team_id="2",
                    status=status,
                    home_score=112 + period,
                    away_score=112 + period,
                    period=period,
                    clock="05:00",
                    is_final=is_final,
                )
            ]
        )

    run_catalog_sync(overtime_provider(4))
    run_catalog_sync(overtime_provider(5))
    run_catalog_sync(overtime_provider(5))
    run_catalog_sync(overtime_provider(6))
    run_catalog_sync(overtime_provider(6))
    run_catalog_sync(overtime_provider(7, status="final", is_final=True))

    alerts = db_session.scalars(
        select(Alert)
        .where(Alert.user_id == enabled_user.id, Alert.alert_type == "overtime_start")
        .order_by(Alert.id.asc())
    ).all()
    assert [alert.event_data["period"] for alert in alerts] == [5, 6]
    assert [alert.event_data["clock"] for alert in alerts] == ["05:00", "05:00"]
    assert [alert.event_data["status"] for alert in alerts] == ["in_progress", "in_progress"]
    assert [alert.event_key for alert in alerts] == [
        f"{enabled_user.id}:{alerts[0].game_id}:overtime_start:5",
        f"{enabled_user.id}:{alerts[1].game_id}:overtime_start:6",
    ]

    disabled_alerts = db_session.scalars(
        select(Alert).where(
            Alert.user_id == disabled_user.id,
            Alert.alert_type == "overtime_start",
        )
    ).all()
    assert disabled_alerts == []


def test_ingest_creates_final_result_alert(db_session):
    user = User(email="final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run_catalog_sync(make_final_provider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-final"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="final_result", is_enabled_override=True))
    db_session.commit()

    run_catalog_sync(make_final_provider())

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert len(sent) == 1
    assert sent[0].alert_type == "final_result"
    assert sent[0].deliveries[0].status == "sent"


def test_wnba_reuses_deduped_basketball_alerts(db_session):
    user = User(email="wnba-alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(competition_teams_query("WNBA").where(Team.external_team_id == "9"))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    for alert_type in ("game_start", "close_game_late", "overtime_start", "final_result"):
        db_session.add(
            UserAlertPreference(
                user_id=user.id,
                sport="basketball",
                alert_type=alert_type,
                is_enabled_override=True,
                close_game_margin_threshold_override=5 if alert_type == "close_game_late" else None,
                close_game_time_threshold_seconds_override=120 if alert_type == "close_game_late" else None,
            )
        )
    db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(minutes=1)
    live_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="in_progress",
                home_score=82,
                away_score=79,
                period=4,
                clock="01:12",
            )
        ]
    )
    run_catalog_sync(live_provider, competition="WNBA")
    run_catalog_sync(live_provider, competition="WNBA")

    overtime_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="in_progress",
                home_score=88,
                away_score=88,
                period=5,
                clock="05:00",
            )
        ]
    )
    run_catalog_sync(overtime_provider, competition="WNBA")
    run_catalog_sync(overtime_provider, competition="WNBA")

    final_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="final",
                home_score=88,
                away_score=80,
                period=4,
                clock="0:00",
                is_final=True,
            )
        ]
    )
    run_catalog_sync(final_provider, competition="WNBA")
    run_catalog_sync(final_provider, competition="WNBA")

    sent = db_session.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.alert_type.asc())
    ).all()
    assert [alert.alert_type for alert in sent] == [
        "close_game_late",
        "final_result",
        "game_start",
        "overtime_start",
    ]


def test_nfl_creates_deduped_football_alerts(db_session):
    user = User(email="nfl-alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(competition_teams_query("NFL").where(Team.external_team_id == "12"))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    for alert_type in ("game_start", "close_game_late", "overtime_start", "final_result"):
        db_session.add(
            UserAlertPreference(
                user_id=user.id,
                sport="football",
                alert_type=alert_type,
                is_enabled_override=True,
                close_game_margin_threshold_override=8 if alert_type == "close_game_late" else None,
                close_game_time_threshold_seconds_override=300 if alert_type == "close_game_late" else None,
            )
        )
    db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(minutes=1)
    live_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-nfl-live",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=start,
                status="in_progress",
                home_score=20,
                away_score=12,
                period=4,
                clock="04:30",
            )
        ]
    )
    run_catalog_sync(live_provider, competition="NFL")
    run_catalog_sync(live_provider, competition="NFL")

    overtime_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-nfl-live",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=start,
                status="in_progress",
                home_score=20,
                away_score=20,
                period=5,
                clock="08:42",
            )
        ]
    )
    run_catalog_sync(overtime_provider, competition="NFL")
    run_catalog_sync(overtime_provider, competition="NFL")

    final_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-nfl-live",
                home_external_team_id="2",
                away_external_team_id="12",
                scheduled_start_time=start,
                status="final",
                home_score=23,
                away_score=20,
                period=5,
                clock="0:00",
                is_final=True,
            )
        ]
    )
    run_catalog_sync(final_provider, competition="NFL")
    run_catalog_sync(final_provider, competition="NFL")

    sent = db_session.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.alert_type.asc())
    ).all()
    assert [alert.alert_type for alert in sent] == [
        "close_game_late",
        "final_result",
        "game_start",
        "overtime_start",
    ]


def test_following_live_game_after_start_does_not_send_game_start_alert(db_session):
    user = User(email="late-follow@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-live-late-follow",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=datetime.now(timezone.utc) - timedelta(minutes=10),
                status="in_progress",
                home_score=100,
                away_score=98,
                period=4,
                clock="01:30",
            )
        ]
    )
    run_catalog_sync(provider)

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live-late-follow"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=True))
    db_session.commit()

    run_catalog_sync(provider)

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert all(row.alert_type != "game_start" for row in sent)


def test_ingest_continues_when_inline_delivery_fails(db_session, monkeypatch):
    user = User(email="inline-fail@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=True))
    db_session.commit()

    def fake_deliver(db, *, alert, delivery, user, game, home, away, service):
        delivery.status = "failed"
        delivery.provider_data = {"error": "synthetic_failure"}
        return "failed"

    monkeypatch.setattr("app.worker.alerts.deliver_email_alert_now", fake_deliver)

    result = run_catalog_sync(make_live_close_provider())
    assert result.alerts_created == 2

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert len(sent) == 2
    assert all(row.deliveries[0].status == "failed" for row in sent)
    assert all(row.deliveries[0].provider_data["error"] == "synthetic_failure" for row in sent)


def test_live_sync_persists_long_clock_values(db_session):
    teams = db_session.scalars(competition_teams_query("NBA").order_by(Team.id.asc())).all()
    run_catalog_sync(
        LongClockProvider(
            home_external_team_id=teams[0].external_team_id,
            away_external_team_id=teams[1].external_team_id,
        )
    )

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-long-clock"))
    assert game is not None
    assert game.clock == "Rain Delay, Bottom 1st"


def test_build_live_requests_includes_previous_scoreboard_date_for_midnight_utc_games(db_session):
    teams = db_session.scalars(competition_teams_query("NBA").order_by(Team.id.asc())).all()
    now = datetime(2026, 6, 11, 1, 0, tzinfo=timezone.utc)
    db_session.add(
        Game(
            external_game_id="nba-midnight-utc",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime(2026, 6, 11, 0, 30, tzinfo=timezone.utc),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    requests = build_live_requests(db_session, "NBA", now=now)
    assert requests == ["20260610", "20260611"]


def test_ingest_respects_game_override_over_competition_default(db_session):
    user = User(email="override@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=True))
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live"))
    assert game is not None

    db_session.add(
        UserGameAlertOverride(
            user_id=user.id,
            game_id=game.id,
            alert_type="game_start",
            is_enabled_override=False,
        )
    )
    db_session.commit()

    db_session.query(AlertDelivery).delete()
    db_session.query(Alert).delete()
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert all(row.alert_type != "game_start" for row in sent)


def test_ingest_excludes_user_game_unfollows_for_team_follows(db_session):
    user = User(email="unfollow-override@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertPreference(user_id=user.id, sport="basketball", alert_type="game_start", is_enabled_override=True))
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live"))
    assert game is not None

    db_session.add(UserGameUnfollow(user_id=user.id, game_id=game.id))
    db_session.commit()

    db_session.query(Alert).delete()
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert len(sent) == 0


def test_ingest_creates_mlb_inning_start_alert(db_session):
    user = User(email="mlb-inning@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    mlb_team = db_session.scalar(competition_teams_query("MLB").where(Team.external_team_id == "2"))
    assert mlb_team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=mlb_team.id))
    db_session.add(
        UserAlertPreference(
            user_id=user.id,
            sport="baseball",
            alert_type="inning_start",
            is_enabled_override=True,
            inning_start_threshold_override=7,
        )
    )
    db_session.commit()

    run_catalog_sync(make_mlb_inning_provider(), competition="MLB")

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert any(row.alert_type == "inning_start" for row in sent)


def test_mlb_extra_innings_alerts_once_per_inning(db_session):
    enabled_user = User(email="extra-innings@example.com")
    disabled_user = User(email="no-extra-innings@example.com")
    db_session.add_all([enabled_user, disabled_user])
    db_session.commit()
    db_session.refresh(enabled_user)
    db_session.refresh(disabled_user)

    team = db_session.scalar(competition_teams_query("MLB").where(Team.external_team_id == "2"))
    assert team is not None
    for user, extra_innings_enabled in ((enabled_user, True), (disabled_user, False)):
        db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
        db_session.add(
            UserAlertPreference(user_id=user.id, sport="baseball", alert_type="game_start", is_enabled_override=False)
        )
        db_session.add(
            UserAlertPreference(user_id=user.id, sport="baseball", alert_type="inning_start", is_enabled_override=False)
        )
        db_session.add(
            UserAlertPreference(
                user_id=user.id,
                sport="baseball",
                alert_type="extra_innings_start",
                is_enabled_override=extra_innings_enabled,
            )
        )
    db_session.commit()

    def extra_innings_provider(
        inning: int,
        *,
        status: str = "in_progress",
        is_final: bool = False,
    ) -> StaticProvider:
        return StaticProvider(
            [
                make_game(
                    external_game_id="game-extra-innings",
                    home_external_team_id="2",
                    away_external_team_id="10",
                    status=status,
                    home_score=3,
                    away_score=3,
                    period=inning,
                    clock=f"Top {inning}th",
                    is_final=is_final,
                )
            ]
        )

    run_catalog_sync(extra_innings_provider(9), competition="MLB")
    run_catalog_sync(extra_innings_provider(10), competition="MLB")
    run_catalog_sync(extra_innings_provider(10), competition="MLB")
    run_catalog_sync(extra_innings_provider(11), competition="MLB")
    run_catalog_sync(extra_innings_provider(11), competition="MLB")
    run_catalog_sync(
        extra_innings_provider(12, status="final", is_final=True),
        competition="MLB",
    )

    alerts = db_session.scalars(
        select(Alert)
        .where(Alert.user_id == enabled_user.id, Alert.alert_type == "extra_innings_start")
        .order_by(Alert.id.asc())
    ).all()
    assert [alert.event_data["period"] for alert in alerts] == [10, 11]
    assert [alert.event_data["clock"] for alert in alerts] == ["Top 10th", "Top 11th"]
    assert [alert.event_data["status"] for alert in alerts] == ["in_progress", "in_progress"]
    assert [alert.event_key for alert in alerts] == [
        f"{enabled_user.id}:{alerts[0].game_id}:extra_innings_start:10",
        f"{enabled_user.id}:{alerts[1].game_id}:extra_innings_start:11",
    ]

    disabled_alerts = db_session.scalars(
        select(Alert).where(
            Alert.user_id == disabled_user.id,
            Alert.alert_type == "extra_innings_start",
        )
    ).all()
    assert disabled_alerts == []
