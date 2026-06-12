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
    groups = preferences_response.json()
    assert len(groups) == 2
    nba_group = next(group for group in groups if group["league"] == "NBA")
    mlb_group = next(group for group in groups if group["league"] == "MLB")
    assert len(nba_group["preferences"]) == 3
    assert {item["alert_type"] for item in nba_group["preferences"]} == {"game_start", "close_game_late", "final_result"}
    assert {item["alert_type"] for item in mlb_group["preferences"]} == {"game_start", "inning_start", "final_result"}

    update_response = client.put(
        "/alert-preferences/leagues/NBA/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 90,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["league"] == "NBA"
    assert updated["alert_type"] == "close_game_late"
    assert updated["close_game_margin_threshold"] == 3
    assert updated["close_game_time_threshold_seconds"] == 90


def test_game_alert_override_flow(client):
    headers = _auth_headers(client, email="m2-game-overrides@example.com")
    game_id = _create_game()

    get_response = client.get(f"/alert-preferences/games/{game_id}", headers=headers)
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["game_id"] == game_id
    assert payload["league"] == "NBA"
    assert len(payload["items"]) == 3
    close_item = next(item for item in payload["items"] if item["alert_type"] == "close_game_late")
    assert close_item["use_league_default"] is True
    assert close_item["close_game_margin_threshold"] == 5
    assert close_item["close_game_time_threshold_seconds"] == 300

    update_response = client.put(
        f"/alert-preferences/games/{game_id}/close_game_late",
        headers=headers,
        json={
            "is_enabled_override": False,
            "close_game_margin_threshold_override": 2,
            "close_game_time_threshold_seconds_override": 45,
        },
    )
    assert update_response.status_code == 200
    updated_item = update_response.json()
    assert updated_item["use_league_default"] is False
    assert updated_item["is_enabled"] is False
    assert updated_item["close_game_margin_threshold"] == 2
    assert updated_item["close_game_time_threshold_seconds"] == 45

    clear_response = client.delete(f"/alert-preferences/games/{game_id}/close_game_late", headers=headers)
    assert clear_response.status_code == 200
    cleared_item = clear_response.json()
    assert cleared_item["use_league_default"] is True
    assert cleared_item["is_enabled"] is True
    assert cleared_item["close_game_margin_threshold"] == 5
    assert cleared_item["close_game_time_threshold_seconds"] == 300
