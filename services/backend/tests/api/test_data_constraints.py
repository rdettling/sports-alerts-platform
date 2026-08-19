from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Alert, AlertDelivery, Team, User, UserTeamFollow
from app.db.session import SessionLocal


def test_user_team_follow_unique_constraint():
    db = SessionLocal()
    user = User(email="u@example.com")
    team = Team(external_team_id="1", league="NBA", name="Atlanta Hawks", abbreviation="ATL")
    db.add_all([user, team])
    db.commit()
    db.refresh(user)
    db.refresh(team)

    db.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db.commit()

    db.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_alert_event_key_unique():
    db = SessionLocal()
    user = User(email="v@example.com")
    home = Team(external_team_id="2", league="NBA", name="Boston Celtics", abbreviation="BOS")
    away = Team(external_team_id="17", league="NBA", name="Brooklyn Nets", abbreviation="BKN")
    db.add_all([user, home, away])
    db.commit()
    db.refresh(user)
    db.refresh(home)
    db.refresh(away)

    from app.db.models import Game

    game = Game(
        external_game_id="game-1",
        league="NBA",
        home_team_id=home.id,
        away_team_id=away.id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="scheduled",
    )
    db.add(game)
    db.commit()
    db.refresh(game)

    payload = dict(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        event_key=f"{user.id}:{game.id}:game_start",
    )
    db.add(Alert(**payload))
    db.commit()

    db.add(Alert(**payload))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_alert_delivery_channel_unique_per_alert():
    db = SessionLocal()
    user = User(email="delivery-constraint@example.com")
    home = Team(external_team_id="constraint-home", league="NBA", name="Home", abbreviation="HOM")
    away = Team(external_team_id="constraint-away", league="NBA", name="Away", abbreviation="AWY")
    db.add_all([user, home, away])
    db.commit()

    from app.db.models import Game

    game = Game(
        external_game_id="delivery-constraint-game",
        league="NBA",
        home_team_id=home.id,
        away_team_id=away.id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="scheduled",
    )
    db.add(game)
    db.commit()
    alert = Alert(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        event_key=f"{user.id}:{game.id}:game_start",
    )
    db.add(alert)
    db.commit()

    db.add(AlertDelivery(alert_id=alert.id, channel="email", status="pending"))
    db.commit()
    db.add(AlertDelivery(alert_id=alert.id, channel="email", status="pending"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
