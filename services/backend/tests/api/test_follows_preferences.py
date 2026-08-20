from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import (
    CompetitionSetting,
    CompetitionTeam,
    Game,
    Team,
    User,
    UserAlertPreference,
    UserGameAlertOverride,
    UserTeamFollow,
)
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query


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


def _create_game(competition: str = "NBA") -> int:
    db = SessionLocal()
    try:
        teams = db.scalars(competition_teams_query(competition).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id=f"test-game-m2-{competition.lower()}",
            competition=competition,
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
            competition="NBA",
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


def test_canonical_team_follow_spans_competitions_and_survives_membership_changes(client):
    headers = _auth_headers(client, email="canonical-team@example.com")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        arsenal = db.scalar(
            competition_teams_query("PREMIER_LEAGUE").where(Team.external_team_id == "359")
        )
        premier_opponent = db.scalar(
            competition_teams_query("PREMIER_LEAGUE").where(Team.external_team_id != "359")
        )
        la_liga_opponent = db.scalar(competition_teams_query("LA_LIGA"))
        mls_opponent = db.scalar(competition_teams_query("MLS"))
        assert arsenal and premier_opponent and la_liga_opponent and mls_opponent

        db.add(CompetitionTeam(competition="LA_LIGA", team_id=arsenal.id))
        games = [
            Game(
                external_game_id="arsenal-premier-test",
                competition="PREMIER_LEAGUE",
                home_team_id=arsenal.id,
                away_team_id=premier_opponent.id,
                scheduled_start_time=now + timedelta(hours=1),
                status="scheduled",
            ),
            Game(
                external_game_id="arsenal-la-liga-test",
                competition="LA_LIGA",
                home_team_id=arsenal.id,
                away_team_id=la_liga_opponent.id,
                scheduled_start_time=now + timedelta(hours=2),
                status="scheduled",
            ),
        ]
        db.add_all(games)
        db.commit()
        arsenal_id = arsenal.id
        premier_game_id, la_liga_game_id = (game.id for game in games)

    arsenal_rows = [team for team in client.get("/teams").json() if team["id"] == arsenal_id]
    assert len(arsenal_rows) == 1
    assert arsenal_rows[0]["sport"] == "soccer"
    assert set(arsenal_rows[0]["competitions"]) == {"PREMIER_LEAGUE", "LA_LIGA"}

    assert client.post(f"/follows/teams/{arsenal_id}", headers=headers).status_code == 201
    followed_game_ids = {game["id"] for game in client.get("/follows", headers=headers).json()["games"]}
    assert {premier_game_id, la_liga_game_id} <= followed_game_ids

    assert client.delete(f"/follows/games/{la_liga_game_id}", headers=headers).status_code == 200
    followed_game_ids = {game["id"] for game in client.get("/follows", headers=headers).json()["games"]}
    assert premier_game_id in followed_game_ids
    assert la_liga_game_id not in followed_game_ids

    with SessionLocal() as db:
        la_liga_membership = db.get(CompetitionTeam, ("LA_LIGA", arsenal_id))
        assert la_liga_membership is not None
        db.delete(la_liga_membership)
        db.add(CompetitionTeam(competition="MLS", team_id=arsenal_id))
        mls_opponent = db.scalar(competition_teams_query("MLS").where(Team.id != arsenal_id))
        assert mls_opponent is not None
        mls_game = Game(
            external_game_id="arsenal-mls-test",
            competition="MLS",
            home_team_id=arsenal_id,
            away_team_id=mls_opponent.id,
            scheduled_start_time=now + timedelta(hours=3),
            status="scheduled",
        )
        db.add(mls_game)
        db.commit()
        mls_game_id = mls_game.id
        assert db.scalar(
            select(UserTeamFollow).where(UserTeamFollow.team_id == arsenal_id)
        ) is not None

    moved_arsenal = next(team for team in client.get("/teams").json() if team["id"] == arsenal_id)
    assert set(moved_arsenal["competitions"]) == {"PREMIER_LEAGUE", "MLS"}
    followed_game_ids = {game["id"] for game in client.get("/follows", headers=headers).json()["games"]}
    assert mls_game_id in followed_game_ids

    with SessionLocal() as db:
        db.get(CompetitionSetting, "MLS").is_enabled = False
        db.commit()

    hidden_arsenal = next(team for team in client.get("/teams").json() if team["id"] == arsenal_id)
    assert hidden_arsenal["competitions"] == ["PREMIER_LEAGUE"]
    follows = client.get("/follows", headers=headers).json()
    assert follows["teams"][0]["id"] == arsenal_id
    assert mls_game_id not in {game["id"] for game in follows["games"]}


def test_alert_preferences_get_and_update(client):
    headers = _auth_headers(client, email="m2-preferences@example.com")

    preferences_response = client.get("/alert-preferences", headers=headers)
    assert preferences_response.status_code == 200
    groups = preferences_response.json()
    assert [group["sport"] for group in groups] == ["basketball", "football", "baseball", "soccer"]
    basketball = next(group for group in groups if group["sport"] == "basketball")
    football = next(group for group in groups if group["sport"] == "football")
    baseball = next(group for group in groups if group["sport"] == "baseball")
    soccer = next(group for group in groups if group["sport"] == "soccer")
    assert {item["alert_type"] for item in basketball["preferences"]} == {
        "game_start",
        "close_game_late",
        "overtime_start",
        "final_result",
    }
    assert {item["alert_type"] for item in football["preferences"]} == {
        "game_start",
        "close_game_late",
        "overtime_start",
        "final_result",
    }
    football_close = next(item for item in football["preferences"] if item["alert_type"] == "close_game_late")
    assert football_close["close_game_margin_threshold"] == 8
    assert {item["alert_type"] for item in baseball["preferences"]} == {
        "game_start",
        "inning_start",
        "extra_innings_start",
        "final_result",
    }
    assert {item["alert_type"] for item in soccer["preferences"]} == {
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    }

    update_response = client.put(
        "/alert-preferences/sports/basketball/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 90,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["sport"] == "basketball"
    assert updated["alert_type"] == "close_game_late"
    assert updated["close_game_margin_threshold"] == 3
    assert updated["close_game_time_threshold_seconds"] == 90

    full_update = client.put(
        "/alert-preferences/sports/basketball/close_game_late",
        headers=headers,
        json={
            "is_enabled": False,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 90,
        },
    )
    assert full_update.status_code == 200
    assert full_update.json()["is_enabled"] is False
    assert full_update.json()["close_game_margin_threshold"] == 3
    assert full_update.json()["close_game_time_threshold_seconds"] == 90

    soccer_update = client.put(
        "/alert-preferences/sports/soccer/penalty_kicks",
        headers=headers,
        json={"is_enabled": False},
    )
    assert soccer_update.status_code == 200
    refreshed = client.get("/alert-preferences", headers=headers).json()
    soccer_penalties = next(
        item
        for group in refreshed
        if group["sport"] == "soccer"
        for item in group["preferences"]
        if item["alert_type"] == "penalty_kicks"
    )
    assert soccer_penalties["is_enabled"] is False

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "m2-preferences@example.com"))
        rows = db.scalars(
            select(UserAlertPreference).where(UserAlertPreference.user_id == user.id)
        ).all()
        assert len(rows) == 2
        basketball_preference = next(row for row in rows if row.sport == "basketball")
        assert basketball_preference.is_enabled_override is False
        assert basketball_preference.close_game_margin_threshold_override == 3
        assert basketball_preference.close_game_time_threshold_seconds_override == 90

    reset = client.put(
        "/alert-preferences/sports/basketball/close_game_late",
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
                UserAlertPreference.sport == "basketball",
            )
        ) is None


def test_alert_preferences_get_does_not_materialize_defaults(client):
    email = "sparse-preferences@example.com"
    headers = _auth_headers(client, email=email)
    response = client.get("/alert-preferences", headers=headers)
    assert response.status_code == 200
    basketball_group = next(group for group in response.json() if group["sport"] == "basketball")
    overtime = next(item for item in basketball_group["preferences"] if item["alert_type"] == "overtime_start")
    assert overtime["is_enabled"] is True
    baseball_group = next(group for group in response.json() if group["sport"] == "baseball")
    extra_innings = next(
        item for item in baseball_group["preferences"] if item["alert_type"] == "extra_innings_start"
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
    assert payload["competition"] == "NBA"
    assert len(payload["items"]) == 4
    close_item = next(item for item in payload["items"] if item["alert_type"] == "close_game_late")
    assert close_item["uses_sport_defaults"] is True
    assert "override" not in close_item
    assert close_item["close_game_margin_threshold"] == 5
    assert close_item["close_game_time_threshold_seconds"] == 300
    overtime_item = next(item for item in payload["items"] if item["alert_type"] == "overtime_start")
    assert overtime_item["is_enabled"] is True
    assert overtime_item["uses_sport_defaults"] is True

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
            "is_enabled": False,
            "close_game_margin_threshold": 2,
            "close_game_time_threshold_seconds": 45,
        },
    )
    assert update_response.status_code == 200
    updated_item = update_response.json()
    assert updated_item["uses_sport_defaults"] is False
    assert updated_item["is_enabled"] is False
    assert updated_item["close_game_margin_threshold"] == 2
    assert updated_item["close_game_time_threshold_seconds"] == 45

    clear_response = client.delete(f"/alert-preferences/games/{game_id}/close_game_late", headers=headers)
    assert clear_response.status_code == 200
    cleared_item = clear_response.json()
    assert cleared_item["uses_sport_defaults"] is True
    assert cleared_item["is_enabled"] is True
    assert cleared_item["close_game_margin_threshold"] == 5
    assert cleared_item["close_game_time_threshold_seconds"] == 300

    overtime_update = client.put(
        f"/alert-preferences/games/{game_id}/overtime_start",
        headers=headers,
        json={"is_enabled": False},
    )
    assert overtime_update.status_code == 200
    assert overtime_update.json()["is_enabled"] is False
    assert overtime_update.json()["uses_sport_defaults"] is False

    overtime_clear = client.delete(f"/alert-preferences/games/{game_id}/overtime_start", headers=headers)
    assert overtime_clear.status_code == 200
    assert overtime_clear.json()["is_enabled"] is True
    assert overtime_clear.json()["uses_sport_defaults"] is True


def test_extra_innings_game_alert_override_flow(client):
    headers = _auth_headers(client, email="mlb-extra-innings-overrides@example.com")
    game_id = _create_game("MLB")

    response = client.get(f"/alert-preferences/games/{game_id}", headers=headers)
    assert response.status_code == 200
    extra_innings = next(
        item for item in response.json()["items"] if item["alert_type"] == "extra_innings_start"
    )
    assert extra_innings["is_enabled"] is True
    assert extra_innings["uses_sport_defaults"] is True

    update = client.put(
        f"/alert-preferences/games/{game_id}/extra_innings_start",
        headers=headers,
        json={"is_enabled": False},
    )
    assert update.status_code == 200
    assert update.json()["is_enabled"] is False
    assert update.json()["uses_sport_defaults"] is False

    clear = client.delete(f"/alert-preferences/games/{game_id}/extra_innings_start", headers=headers)
    assert clear.status_code == 200
    assert clear.json()["is_enabled"] is True
    assert clear.json()["uses_sport_defaults"] is True


def test_noop_game_alert_overrides_are_not_stored(client):
    email = "noop-game-overrides@example.com"
    headers = _auth_headers(client, email=email)
    game_id = _create_game()

    competition_update = client.put(
        "/alert-preferences/sports/basketball/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 300,
        },
    )
    assert competition_update.status_code == 200

    equivalent = client.put(
        f"/alert-preferences/games/{game_id}/close_game_late",
        headers=headers,
        json={
            "is_enabled": True,
            "close_game_margin_threshold": 3,
            "close_game_time_threshold_seconds": 300,
        },
    )
    assert equivalent.status_code == 200
    assert equivalent.json()["uses_sport_defaults"] is True
    assert "override" not in equivalent.json()

    empty = client.put(
        f"/alert-preferences/games/{game_id}/close_game_late",
        headers=headers,
        json={},
    )
    assert empty.status_code == 422

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert db.scalar(
            select(UserGameAlertOverride).where(
                UserGameAlertOverride.user_id == user.id,
                UserGameAlertOverride.game_id == game_id,
            )
        ) is None


def test_game_settings_inherit_only_fields_without_overrides(client):
    headers = _auth_headers(client, email="per-field-inheritance@example.com")
    game_id = _create_game()
    competition_url = "/alert-preferences/sports/basketball/close_game_late"
    game_url = f"/alert-preferences/games/{game_id}/close_game_late"

    assert (
        client.put(
            competition_url,
            headers=headers,
            json={
                "is_enabled": True,
                "close_game_margin_threshold": 3,
                "close_game_time_threshold_seconds": 90,
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            game_url,
            headers=headers,
            json={
                "is_enabled": False,
                "close_game_margin_threshold": 3,
                "close_game_time_threshold_seconds": 45,
            },
        ).status_code
        == 200
    )

    assert (
        client.put(
            competition_url,
            headers=headers,
            json={
                "is_enabled": True,
                "close_game_margin_threshold": 4,
                "close_game_time_threshold_seconds": 120,
            },
        ).status_code
        == 200
    )
    item = next(
        item
        for item in client.get(
            f"/alert-preferences/games/{game_id}", headers=headers
        ).json()["items"]
        if item["alert_type"] == "close_game_late"
    )

    assert item["uses_sport_defaults"] is False
    assert item["is_enabled"] is False
    assert item["close_game_margin_threshold"] == 4
    assert item["close_game_time_threshold_seconds"] == 45


@pytest.mark.parametrize(
    ("sport", "alert_type", "payload"),
    [
        ("basketball", "game_start", {}),
        ("basketball", "game_start", {"is_enabled": True, "is_enabled_override": False}),
        ("basketball", "game_start", {"is_enabled": True, "inning_start_threshold": 7}),
        ("basketball", "close_game_late", {"is_enabled": True}),
        ("baseball", "inning_start", {"is_enabled": True}),
        (
            "baseball",
            "inning_start",
            {
                "is_enabled": True,
                "inning_start_threshold": 7,
                "close_game_margin_threshold": 3,
            },
        ),
    ],
)
def test_alert_settings_reject_incomplete_or_irrelevant_fields(
    client, sport, alert_type, payload
):
    headers = _auth_headers(client, email=f"invalid-{sport}-{alert_type}@example.com")

    response = client.put(
        f"/alert-preferences/sports/{sport}/{alert_type}",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422


def test_inning_settings_use_the_shared_concrete_shape(client):
    headers = _auth_headers(client, email="inning-settings@example.com")
    game_id = _create_game("MLB")

    response = client.put(
        f"/alert-preferences/games/{game_id}/inning_start",
        headers=headers,
        json={"is_enabled": True, "inning_start_threshold": 5},
    )

    assert response.status_code == 200
    assert response.json()["uses_sport_defaults"] is False
    assert response.json()["inning_start_threshold"] == 5
