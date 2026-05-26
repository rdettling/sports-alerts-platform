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


def _create_game_for_team(team_id: int) -> int:
    db = SessionLocal()
    try:
        opponent = db.scalar(select(Team).where(Team.id != team_id).order_by(Team.id.asc()))
        assert opponent is not None
        game = Game(
            external_game_id=f"test-team-game-{team_id}-{datetime.now(timezone.utc).timestamp()}",
            league="NBA",
            home_team_id=team_id,
            away_team_id=opponent.id,
            scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=4),
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


def test_team_follow_includes_team_games_with_per_game_override(client):
    headers = _auth_headers(client, email="m2-team-games@example.com")
    teams_response = client.get("/teams")
    assert teams_response.status_code == 200
    team_id = teams_response.json()[0]["id"]

    game_id = _create_game_for_team(team_id)

    follow_team_response = client.post(f"/follows/teams/{team_id}", headers=headers)
    assert follow_team_response.status_code == 201

    follows_response = client.get("/follows", headers=headers)
    assert follows_response.status_code == 200
    game_ids = [game["id"] for game in follows_response.json()["games"]]
    assert game_id in game_ids

    unfollow_game_response = client.delete(f"/follows/games/{game_id}", headers=headers)
    assert unfollow_game_response.status_code == 200
    assert unfollow_game_response.json()["status"] == "unfollowed"

    follows_response_after_game_unfollow = client.get("/follows", headers=headers)
    assert follows_response_after_game_unfollow.status_code == 200
    game_ids_after_unfollow = [game["id"] for game in follows_response_after_game_unfollow.json()["games"]]
    assert game_id not in game_ids_after_unfollow

    follow_game_response = client.post(f"/follows/games/{game_id}", headers=headers)
    assert follow_game_response.status_code == 201
    assert follow_game_response.json()["status"] in {"followed", "already_following"}

    follows_response_after_refollow = client.get("/follows", headers=headers)
    assert follows_response_after_refollow.status_code == 200
    game_ids_after_refollow = [game["id"] for game in follows_response_after_refollow.json()["games"]]
    assert game_id in game_ids_after_refollow


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
