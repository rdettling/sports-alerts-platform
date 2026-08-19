from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Game, Team, User, UserAlertPreference, UserGameAlertOverride
from app.db.session import SessionLocal


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


def _create_game(league: str = "NBA") -> int:
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).where(Team.league == league).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id=f"test-game-m2-{league.lower()}",
            league=league,
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
    assert len(groups) == 6
    nba_group = next(group for group in groups if group["league"] == "NBA")
    wnba_group = next(group for group in groups if group["league"] == "WNBA")
    nfl_group = next(group for group in groups if group["league"] == "NFL")
    mlb_group = next(group for group in groups if group["league"] == "MLB")
    mls_group = next(group for group in groups if group["league"] == "MLS")
    world_cup_group = next(group for group in groups if group["league"] == "WORLD_CUP")
    assert len(nba_group["preferences"]) == 4
    assert {item["alert_type"] for item in nba_group["preferences"]} == {
        "game_start",
        "close_game_late",
        "overtime_start",
        "final_result",
    }
    assert {item["alert_type"] for item in wnba_group["preferences"]} == {
        "game_start",
        "close_game_late",
        "overtime_start",
        "final_result",
    }
    assert next(item for item in nba_group["preferences"] if item["alert_type"] == "overtime_start")["is_enabled"] is True
    assert {item["alert_type"] for item in nfl_group["preferences"]} == {
        "game_start",
        "close_game_late",
        "overtime_start",
        "final_result",
    }
    nfl_close = next(item for item in nfl_group["preferences"] if item["alert_type"] == "close_game_late")
    assert nfl_close["close_game_margin_threshold"] == 8
    assert nfl_close["close_game_time_threshold_seconds"] == 300
    assert {item["alert_type"] for item in mlb_group["preferences"]} == {
        "game_start",
        "inning_start",
        "extra_innings_start",
        "final_result",
    }
    assert next(item for item in mlb_group["preferences"] if item["alert_type"] == "extra_innings_start")["is_enabled"] is True
    assert {item["alert_type"] for item in mls_group["preferences"]} == {
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    }
    assert all(item["is_enabled"] for item in mls_group["preferences"])
    assert {item["alert_type"] for item in world_cup_group["preferences"]} == {"game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"}

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

    partial_update = client.put(
        "/alert-preferences/leagues/NBA/close_game_late",
        headers=headers,
        json={"is_enabled": False},
    )
    assert partial_update.status_code == 200
    assert partial_update.json()["is_enabled"] is False
    assert partial_update.json()["close_game_margin_threshold"] == 3
    assert partial_update.json()["close_game_time_threshold_seconds"] == 90

    mls_update = client.put(
        "/alert-preferences/leagues/MLS/penalty_kicks",
        headers=headers,
        json={"is_enabled": False},
    )
    assert mls_update.status_code == 200
    refreshed = client.get("/alert-preferences", headers=headers).json()
    mls_penalties = next(
        item
        for group in refreshed
        if group["league"] == "MLS"
        for item in group["preferences"]
        if item["alert_type"] == "penalty_kicks"
    )
    world_cup_penalties = next(
        item
        for group in refreshed
        if group["league"] == "WORLD_CUP"
        for item in group["preferences"]
        if item["alert_type"] == "penalty_kicks"
    )
    assert mls_penalties["is_enabled"] is False
    assert world_cup_penalties["is_enabled"] is True

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "m2-preferences@example.com"))
        rows = db.scalars(
            select(UserAlertPreference).where(UserAlertPreference.user_id == user.id)
        ).all()
        assert len(rows) == 2
        nba_preference = next(row for row in rows if row.league == "NBA")
        assert nba_preference.is_enabled_override is False
        assert nba_preference.close_game_margin_threshold_override == 3
        assert nba_preference.close_game_time_threshold_seconds_override == 90

    reset = client.put(
        "/alert-preferences/leagues/NBA/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 5,
            "close_game_time_threshold_seconds": 300,
        },
    )
    assert reset.status_code == 200
    assert reset.json()["close_game_margin_threshold"] == 5
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "m2-preferences@example.com"))
        assert db.scalar(
            select(UserAlertPreference).where(
                UserAlertPreference.user_id == user.id,
                UserAlertPreference.league == "NBA",
            )
        ) is None


def test_alert_preferences_get_does_not_materialize_defaults(client):
    email = "sparse-preferences@example.com"
    headers = _auth_headers(client, email=email)
    response = client.get("/alert-preferences", headers=headers)
    assert response.status_code == 200
    nba_group = next(group for group in response.json() if group["league"] == "NBA")
    overtime = next(item for item in nba_group["preferences"] if item["alert_type"] == "overtime_start")
    assert overtime["is_enabled"] is True
    mlb_group = next(group for group in response.json() if group["league"] == "MLB")
    extra_innings = next(
        item for item in mlb_group["preferences"] if item["alert_type"] == "extra_innings_start"
    )
    assert extra_innings["is_enabled"] is True

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert db.scalars(
            select(UserAlertPreference).where(UserAlertPreference.user_id == user.id)
        ).all() == []


def test_game_alert_override_flow(client):
    headers = _auth_headers(client, email="m2-game-overrides@example.com")
    game_id = _create_game()

    get_response = client.get(f"/alert-preferences/games/{game_id}", headers=headers)
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["game_id"] == game_id
    assert payload["league"] == "NBA"
    assert len(payload["items"]) == 4
    close_item = next(item for item in payload["items"] if item["alert_type"] == "close_game_late")
    assert close_item["use_league_default"] is True
    assert close_item["close_game_margin_threshold"] == 5
    assert close_item["close_game_time_threshold_seconds"] == 300
    overtime_item = next(item for item in payload["items"] if item["alert_type"] == "overtime_start")
    assert overtime_item["is_enabled"] is True
    assert overtime_item["use_league_default"] is True

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "m2-game-overrides@example.com"))
        assert db.scalars(
            select(UserAlertPreference).where(UserAlertPreference.user_id == user.id)
        ).all() == []
        assert db.scalars(
            select(UserGameAlertOverride).where(UserGameAlertOverride.user_id == user.id)
        ).all() == []

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

    overtime_update = client.put(
        f"/alert-preferences/games/{game_id}/overtime_start",
        headers=headers,
        json={"is_enabled_override": False},
    )
    assert overtime_update.status_code == 200
    assert overtime_update.json()["is_enabled"] is False
    assert overtime_update.json()["use_league_default"] is False

    overtime_clear = client.delete(f"/alert-preferences/games/{game_id}/overtime_start", headers=headers)
    assert overtime_clear.status_code == 200
    assert overtime_clear.json()["is_enabled"] is True
    assert overtime_clear.json()["use_league_default"] is True


def test_extra_innings_game_alert_override_flow(client):
    headers = _auth_headers(client, email="mlb-extra-innings-overrides@example.com")
    game_id = _create_game("MLB")

    response = client.get(f"/alert-preferences/games/{game_id}", headers=headers)
    assert response.status_code == 200
    extra_innings = next(
        item for item in response.json()["items"] if item["alert_type"] == "extra_innings_start"
    )
    assert extra_innings["is_enabled"] is True
    assert extra_innings["use_league_default"] is True

    update = client.put(
        f"/alert-preferences/games/{game_id}/extra_innings_start",
        headers=headers,
        json={"is_enabled_override": False},
    )
    assert update.status_code == 200
    assert update.json()["is_enabled"] is False
    assert update.json()["use_league_default"] is False

    clear = client.delete(f"/alert-preferences/games/{game_id}/extra_innings_start", headers=headers)
    assert clear.status_code == 200
    assert clear.json()["is_enabled"] is True
    assert clear.json()["use_league_default"] is True


def test_noop_game_alert_overrides_are_not_stored(client):
    email = "noop-game-overrides@example.com"
    headers = _auth_headers(client, email=email)
    game_id = _create_game()

    league_update = client.put(
        "/alert-preferences/leagues/NBA/close_game_late",
        headers=headers,
        json={"close_game_margin_threshold": 3},
    )
    assert league_update.status_code == 200

    equivalent = client.put(
        f"/alert-preferences/games/{game_id}/close_game_late",
        headers=headers,
        json={
            "is_enabled_override": True,
            "close_game_margin_threshold_override": 3,
            "close_game_time_threshold_seconds_override": 300,
        },
    )
    assert equivalent.status_code == 200
    assert equivalent.json()["use_league_default"] is True
    assert equivalent.json()["override"] is None

    empty = client.put(
        f"/alert-preferences/games/{game_id}/close_game_late",
        headers=headers,
        json={},
    )
    assert empty.status_code == 200
    assert empty.json()["use_league_default"] is True

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert db.scalar(
            select(UserGameAlertOverride).where(
                UserGameAlertOverride.user_id == user.id,
                UserGameAlertOverride.game_id == game_id,
            )
        ) is None
