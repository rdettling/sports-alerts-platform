from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Game, Team
from app.db.session import SessionLocal
from app.db.models import User


def _auth_headers(client, email: str = "m2@example.com") -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _create_game() -> int:
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id="test-game-m2",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            status="scheduled",
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        return game.id
    finally:
        db.close()


def test_team_follow_flow(client):
    headers = _auth_headers(client)
    teams_response = client.get("/teams")
    team_id = teams_response.json()[0]["id"]

    empty_follows = client.get("/follows", headers=headers)
    assert empty_follows.status_code == 200
    assert empty_follows.json()["teams"] == []
    assert empty_follows.json()["games"] == []

    follow_response = client.post(f"/follows/teams/{team_id}", headers=headers)
    assert follow_response.status_code == 201
    assert follow_response.json()["status"] in {"followed", "already_following"}

    follows_response = client.get("/follows", headers=headers)
    assert follows_response.status_code == 200
    assert len(follows_response.json()["teams"]) == 1
    assert follows_response.json()["teams"][0]["id"] == team_id

    unfollow_response = client.delete(f"/follows/teams/{team_id}", headers=headers)
    assert unfollow_response.status_code == 200
    assert unfollow_response.json()["status"] == "unfollowed"


def test_game_follow_flow(client):
    headers = _auth_headers(client, email="m2-games@example.com")
    game_id = _create_game()

    follow_response = client.post(f"/follows/games/{game_id}", headers=headers)
    assert follow_response.status_code == 201
    assert follow_response.json()["status"] in {"followed", "already_following"}

    follows_response = client.get("/follows", headers=headers)
    assert follows_response.status_code == 200
    assert len(follows_response.json()["games"]) == 1
    assert follows_response.json()["games"][0]["id"] == game_id

    unfollow_response = client.delete(f"/follows/games/{game_id}", headers=headers)
    assert unfollow_response.status_code == 200
    assert unfollow_response.json()["status"] == "unfollowed"


def test_alert_preferences_get_and_update(client):
    headers = _auth_headers(client, email="m2-preferences@example.com")

    preferences_response = client.get("/alert-preferences", headers=headers)
    assert preferences_response.status_code == 200
    assert len(preferences_response.json()) == 3

    update_response = client.put(
        "/alert-preferences/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 90,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["alert_type"] == "close_game_late"
    assert updated["close_game_margin_threshold"] == 3
    assert updated["close_game_time_threshold_seconds"] == 90
