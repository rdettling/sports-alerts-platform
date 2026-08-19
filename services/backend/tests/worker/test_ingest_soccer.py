from sqlalchemy import select

from app.db.models import Alert, Team, User, UserAlertPreference, UserTeamFollow
from app.worker.ingest import run_catalog_sync

from ingest_support import SequenceWorldCupProvider, StaticProvider, make_game


def test_world_cup_score_changed_creates_inferred_goal_alert(db_session):
    user = User(email="world-cup-score@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "10'"},
            {"home_score": 0, "away_score": 1, "period": 1, "clock": "18'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "score_changed")).all()
    assert len(sent) == 1
    assert sent[0].event_data["is_inferred_goal"] is True
    assert sent[0].event_data["scoring_side"] == "away"
    assert sent[0].event_data["new_away_score"] == 1
    assert sent[0].event_data["new_home_score"] == 0


def test_world_cup_score_changed_creates_generic_alert_for_ambiguous_jump(db_session):
    user = User(email="world-cup-score-ambiguous@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "60'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "68'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "score_changed")).all()
    assert len(sent) == 1
    assert sent[0].event_data["is_inferred_goal"] is False
    assert sent[0].event_data["scoring_side"] is None


def test_world_cup_score_changed_ignores_score_decreases(db_session):
    user = User(email="world-cup-score-decrease@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "60'"},
            {"home_score": 1, "away_score": 0, "period": 2, "clock": "61'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "score_changed")).all()
    assert len(sent) == 0


def test_world_cup_second_half_start_alert_triggers_once_on_resume(db_session):
    user = User(email="world-cup-second-half@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="second_half_start", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "44'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "HT"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "46'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "48'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "second_half_start")).all()
    assert len(sent) == 1
    assert sent[0].event_data["period"] == 2
    assert sent[0].event_data["clock"] == "46'"


def test_world_cup_second_half_start_does_not_trigger_at_halftime(db_session):
    user = User(email="world-cup-halftime@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="second_half_start", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "44'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "HT"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "second_half_start")).all()
    assert len(sent) == 0


def test_world_cup_extra_time_start_alert_triggers_once_on_period_three_transition(db_session):
    user = User(email="world-cup-extra-time@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="extra_time_start", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "ET"},
            {"home_score": 2, "away_score": 2, "period": 3, "clock": "91'"},
            {"home_score": 2, "away_score": 2, "period": 3, "clock": "94'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "extra_time_start")).all()
    assert len(sent) == 1
    assert sent[0].event_data["period"] == 3
    assert sent[0].event_data["clock"] == "91'"


def test_world_cup_extra_time_start_does_not_trigger_before_period_three(db_session):
    user = User(email="world-cup-extra-time-blocked@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="extra_time_start", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "ET"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "extra_time_start")).all()
    assert len(sent) == 0


def test_world_cup_transition_logging_captures_stoppage_and_extra_time_states(db_session, caplog):
    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "ET"},
        ]
    )

    with caplog.at_level("INFO", logger="app.worker.soccer"):
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    assert "Soccer state transition external_game_id=game-world-cup-live" in caplog.text
    assert "period=2->3" in caplog.text
    assert "90+5'" in caplog.text
    assert "ET" in caplog.text
    assert "extra_time=False->True" in caplog.text
    assert "extra_time_started=True" in caplog.text
    assert "second_half_live=True->False" in caplog.text


def test_world_cup_penalty_kicks_alert_triggers_once_in_late_tied_extra_time(db_session):
    user = User(email="world-cup-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="penalty_kicks", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "117'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "118'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "penalty_kicks")).all()
    assert len(sent) == 1
    assert sent[0].event_data["period"] == 3
    assert sent[0].event_data["clock"] == "117'"


def test_world_cup_penalty_kicks_alert_does_not_trigger_before_threshold_or_without_tie(db_session):
    user = User(email="world-cup-penalties-blocked@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="WORLD_CUP", alert_type="penalty_kicks", is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 2, "away_score": 1, "period": 3, "clock": "117'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "penalty_kicks")).all()
    assert len(sent) == 0


def test_world_cup_transition_logging_marks_penalty_kicks_window(db_session, caplog):
    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "117'"},
        ]
    )

    with caplog.at_level("INFO", logger="app.worker.soccer"):
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    assert "Soccer state transition external_game_id=game-world-cup-live" in caplog.text
    assert "period=3->3" in caplog.text
    assert "penalty_kicks_window=False->True" in caplog.text


def test_mls_direct_shootout_triggers_penalties_without_extra_time_or_score_change(db_session):
    user = User(email="mls-direct-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type="game_start", is_enabled_override=False))
    for alert_type in ("extra_time_start", "penalty_kicks", "score_changed"):
        db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 5, "clock": "93'"},
            {"home_score": 2, "away_score": 2, "period": 5, "clock": "96'"},
        ],
        external_game_id="game-mls-direct-penalties",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(3):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert [alert.alert_type for alert in alerts] == ["penalty_kicks"]
    assert alerts[0].event_data["period"] == 5


def test_mls_extra_time_then_shootout_triggers_each_phase_once(db_session):
    user = User(email="mls-extra-time-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type="game_start", is_enabled_override=False))
    for alert_type in ("extra_time_start", "penalty_kicks"):
        db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "91'"},
            {"home_score": 1, "away_score": 1, "period": 5, "clock": "Pens"},
            {"home_score": 1, "away_score": 1, "period": 5, "clock": "Pens"},
        ],
        external_game_id="game-mls-extra-time-penalties",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(4):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.id.asc())
    ).all()
    assert [alert.alert_type for alert in alerts] == ["extra_time_start", "penalty_kicks"]


def test_mls_second_half_and_goal_use_shared_soccer_events(db_session):
    user = User(email="mls-shared-soccer-events@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type="game_start", is_enabled_override=False))
    for alert_type in ("second_half_start", "score_changed"):
        db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled_override=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "45+2'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "46'"},
            {"home_score": 1, "away_score": 0, "period": 2, "clock": "52'"},
        ],
        external_game_id="game-mls-shared-soccer-events",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(3):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.id.asc())
    ).all()
    assert [alert.alert_type for alert in alerts] == ["second_half_start", "score_changed"]
    assert alerts[1].event_data["scoring_side"] == "home"


def test_mls_final_result_uses_shared_soccer_alert_set(db_session):
    user = User(email="mls-final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type="game_start", is_enabled_override=False))
    db_session.add(UserAlertPreference(user_id=user.id, league="MLS", alert_type="final_result", is_enabled_override=True))
    db_session.commit()

    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-mls-final",
                home_external_team_id="187",
                away_external_team_id="18966",
                status="final",
                home_score=2,
                away_score=1,
                period=2,
                clock="FT",
                is_final=True,
            )
        ]
    )
    assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    assert [alert.alert_type for alert in alerts] == ["final_result"]
