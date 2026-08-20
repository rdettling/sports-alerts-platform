from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Alert, AlertDelivery, Team, User, UserTeamFollow
from app.db.session import SessionLocal


def _team(external_team_id: str, name: str, abbreviation: str) -> Team:
    return Team(
        sport="basketball",
        provider_scope="constraints",
        external_team_id=external_team_id,
        name=name,
        abbreviation=abbreviation,
    )


def test_user_team_follow_unique_constraint():
    db = SessionLocal()
    user = User(email="u@example.com")
    team = _team("1", "Atlanta Hawks", "ATL")
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
    home = _team("2", "Boston Celtics", "BOS")
    away = _team("17", "Brooklyn Nets", "BKN")
    db.add_all([user, home, away])
    db.commit()
    db.refresh(user)
    db.refresh(home)
    db.refresh(away)

    from app.db.models import Game

    game = Game(
        external_game_id="game-1",
        competition="NBA",
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
    home = _team("constraint-home", "Home", "HOM")
    away = _team("constraint-away", "Away", "AWY")
    db.add_all([user, home, away])
    db.commit()

    from app.db.models import Game

    game = Game(
        external_game_id="delivery-constraint-game",
        competition="NBA",
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
