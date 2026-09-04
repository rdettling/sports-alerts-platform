from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import CompetitionSetting, CompetitionTeam, Game, GameOddsCurrent, GameOddsOutcomeCurrent, Team
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query


def _create_game(*, broadcast_names: list[str] | None = None) -> Game:
    db = SessionLocal()
    try:
        teams = db.scalars(competition_teams_query("NBA").order_by(Team.id.asc()).limit(2)).all()
        home_membership = db.get(CompetitionTeam, ("NBA", teams[0].id))
        away_membership = db.get(CompetitionTeam, ("NBA", teams[1].id))
        assert home_membership is not None
        assert away_membership is not None
        home_membership.wins = 48
        home_membership.losses = 31
        home_membership.ties = 0
        away_membership.wins = 57
        away_membership.losses = 22
        away_membership.ties = 0
        game = Game(
            external_game_id="test-odds-game",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            broadcast_names=list(broadcast_names or []),
            status="scheduled",
            is_final=False,
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        return game
    finally:
        db.close()


def _create_old_game() -> None:
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        old_game = Game(
            external_game_id="test-old-game",
            competition="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc) - timedelta(days=10),
            status="scheduled",
            is_final=False,
        )
        db.add(old_game)
        db.commit()
    finally:
        db.close()


def test_games_include_odds_when_available(client):
    game = _create_game()
    db = SessionLocal()
    try:
        odds = GameOddsCurrent(
            game_id=game.id,
            bookmaker="DraftKings",
            fetched_at=datetime.now(timezone.utc),
        )
        odds.outcomes.extend(
            [
                GameOddsOutcomeCurrent(outcome_key="atlanta_hawks", outcome_label="Atlanta Hawks", outcome_order=0, price_american=125, team_side="away"),
                GameOddsOutcomeCurrent(outcome_key="boston_celtics", outcome_label="Boston Celtics", outcome_order=1, price_american=-145, team_side="home"),
            ]
        )
        db.add(odds)
        db.commit()
    finally:
        db.close()

    response = client.get("/games")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["context_label"] is None
    assert payload[0]["home_team_strength"] == {"wins": 48, "losses": 31, "ties": 0, "rank": None}
    assert payload[0]["away_team_strength"] == {"wins": 57, "losses": 22, "ties": 0, "rank": None}
    assert payload[0]["home_team"]["id"] == payload[0]["home_team_id"]
    assert payload[0]["away_team"]["id"] == payload[0]["away_team_id"]
    assert payload[0]["home_team"]["name"]
    assert payload[0]["away_team"]["name"]
    assert payload[0]["broadcast_names"] == []
    assert payload[0]["odds"]["outcomes"][0]["price_american"] == 125
    assert payload[0]["odds"]["outcomes"][0]["team_side"] == "away"
    assert payload[0]["odds"]["outcomes"][1]["price_american"] == -145
    assert payload[0]["odds"]["outcomes"][1]["team_side"] == "home"
    assert payload[0]["odds"]["bookmaker"] == "DraftKings"


def test_games_include_broadcast_names(client):
    _create_game(broadcast_names=["ESPN", "Peacock"])

    response = client.get("/games")

    assert response.status_code == 200
    assert response.json()[0]["broadcast_names"] == ["ESPN", "Peacock"]


def test_games_embed_incidental_fbs_opponents_without_catalog_membership(client):
    with SessionLocal() as db:
        home = db.scalar(
            competition_teams_query("FBS").where(Team.external_team_id == "333")
        )
        assert home is not None
        opponent = Team(
            sport="football",
            provider_scope="cfb",
            external_team_id="999999",
            name="Example State Bears",
            abbreviation="EXST",
        )
        db.add(opponent)
        db.flush()
        db.add(
            Game(
                external_game_id="fbs-vs-fcs-api",
                competition="FBS",
                home_team_id=home.id,
                away_team_id=opponent.id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
                status="scheduled",
                is_final=False,
            )
        )
        db.commit()

    payload = client.get("/games?competition=FBS").json()

    assert len(payload) == 1
    assert payload[0]["away_team"] == {
        "id": payload[0]["away_team_id"],
        "sport": "football",
        "external_team_id": "999999",
        "name": "Example State Bears",
        "abbreviation": "EXST",
        "conference": None,
    }
    assert payload[0]["away_team_strength"] == {
        "wins": None,
        "losses": None,
        "ties": None,
        "rank": None,
    }
    assert all(team["id"] != payload[0]["away_team_id"] for team in client.get("/teams").json())


def test_games_include_world_cup_draw_odds(client):
    db = SessionLocal()
    try:
        teams = db.scalars(competition_teams_query("WORLD_CUP").order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id="test-world-cup-odds",
            competition="WORLD_CUP",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            status="scheduled",
            is_final=False,
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        odds = GameOddsCurrent(
            game_id=game.id,
            bookmaker="DraftKings",
            fetched_at=datetime.now(timezone.utc),
        )
        odds.outcomes.extend(
            [
                GameOddsOutcomeCurrent(outcome_key="united_states", outcome_label="United States", outcome_order=0, price_american=160, team_side="away"),
                GameOddsOutcomeCurrent(outcome_key="draw", outcome_label="Draw", outcome_order=1, price_american=210, team_side=None),
                GameOddsOutcomeCurrent(outcome_key="mexico", outcome_label="Mexico", outcome_order=2, price_american=180, team_side="home"),
            ]
        )
        db.add(odds)
        db.commit()
    finally:
        db.close()

    response = client.get("/games?competition=WORLD_CUP")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert [item["outcome_key"] for item in payload[0]["odds"]["outcomes"]] == ["united_states", "draw", "mexico"]


def test_games_excludes_rows_outside_retention_window(client):
    _create_game()
    _create_old_game()
    response = client.get("/games")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["external_game_id"] == "test-odds-game"


def test_games_supports_competition_filter(client):
    _create_game()
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        db.add(
            Game(
                external_game_id="test-mlb-game",
                competition="MLB",
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=3),
                status="scheduled",
                is_final=False,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/games?competition=NBA")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["competition"] == "NBA"


def test_games_include_finals_when_requested(client):
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        db.add(
            Game(
                external_game_id="test-final-game",
                competition="MLB",
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                scheduled_start_time=datetime.now(timezone.utc) - timedelta(hours=1),
                status="final",
                is_final=True,
            )
        )
        db.commit()
    finally:
        db.close()

    default_response = client.get("/games?competition=MLB")
    assert default_response.status_code == 200
    default_ids = {row["external_game_id"] for row in default_response.json()}
    assert "test-final-game" not in default_ids

    include_response = client.get("/games?competition=MLB&include_finals=true&limit=200")
    assert include_response.status_code == 200
    include_ids = {row["external_game_id"] for row in include_response.json()}
    assert "test-final-game" in include_ids


def test_games_hide_disabled_competition(client):
    db = SessionLocal()
    try:
        settings = db.get(CompetitionSetting, "MLB")
        assert settings is not None
        settings.is_enabled = False
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        db.add(
            Game(
                external_game_id="hidden-mlb-game",
                competition="MLB",
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
                status="scheduled",
                is_final=False,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/games")
    assert response.status_code == 200
    assert {row["external_game_id"] for row in response.json()} == set()


def test_games_return_context_label(client):
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        db.add(
            Game(
                external_game_id="test-context-game",
                competition="NBA",
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
                context_label="NBA Finals - Game 5 · NY leads series 3-1",
                status="scheduled",
                is_final=False,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/games?competition=NBA")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["context_label"] == "NBA Finals - Game 5 · NY leads series 3-1"


def test_games_filter_by_wnba(client):
    db = SessionLocal()
    try:
        teams = db.scalars(competition_teams_query("WNBA").order_by(Team.id.asc()).limit(2)).all()
        db.add(
            Game(
                external_game_id="test-wnba-game",
                competition="WNBA",
                home_team_id=teams[0].id,
                away_team_id=teams[1].id,
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
                status="scheduled",
                is_final=False,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/games?competition=WNBA")

    assert response.status_code == 200
    assert [game["external_game_id"] for game in response.json()] == ["test-wnba-game"]


def test_games_accepts_raised_dashboard_limit(client):
    assert client.get("/games?limit=500").status_code == 200
    assert client.get("/games?limit=501").status_code == 422


DASHBOARD_GAMES_URL = "/games?include_finals=true&limit=500"


def test_dashboard_cache_invalidates_before_worker_broadcast(client, monkeypatch):
    from app.config import settings
    from app.services.live_updates import game_updates

    game = _create_game()
    first = client.get(DASHBOARD_GAMES_URL)
    assert first.headers["cache-control"] == "no-store"
    assert first.json()[0]["home_score"] is None
    with SessionLocal() as db:
        db.get(Game, game.id).home_score = 12
        db.commit()
    assert client.get(DASHBOARD_GAMES_URL).json()[0]["home_score"] is None
    assert client.get("/games?competition=NBA").json()[0]["home_score"] == 12

    monkeypatch.setattr(settings, "live_update_secret", "test-secret")
    seen = []

    def publish(event):
        from app.services.game_feed import game_feed_cache
        seen.append(game_feed_cache.get()[0].home_score)

    monkeypatch.setattr(game_updates, "publish", publish)
    assert client.post(
        "/internal/updates/games",
        headers={"X-Live-Update-Secret": "wrong"},
        json={"competition": "NBA"},
    ).status_code == 401
    assert client.get(DASHBOARD_GAMES_URL).json()[0]["home_score"] is None
    assert client.post(
        "/internal/updates/games",
        headers={"X-Live-Update-Secret": "test-secret"},
        json={"competition": "NBA"},
    ).status_code == 204
    assert seen == [12]
    assert client.get(DASHBOARD_GAMES_URL).json()[0]["home_score"] == 12


def test_competition_toggle_invalidates_dashboard_cache(client):
    from app.deps import require_admin_user
    from app.main import app

    _create_game()
    assert len(client.get(DASHBOARD_GAMES_URL).json()) == 1
    app.dependency_overrides[require_admin_user] = lambda: None
    try:
        for enabled, count in [(False, 0), (True, 1)]:
            assert client.put("/ops/competitions/NBA", json={"is_enabled": enabled}).status_code == 200
            assert len(client.get(DASHBOARD_GAMES_URL).json()) == count
    finally:
        app.dependency_overrides.pop(require_admin_user)


def test_dashboard_cache_is_not_used_for_other_query_shapes(client):
    game = _create_game()
    assert client.get(DASHBOARD_GAMES_URL).json()[0]["status"] == "scheduled"
    with SessionLocal() as db:
        row = db.get(Game, game.id)
        row.status = "final"
        row.is_final = True
        db.commit()
    assert client.get("/games").json() == []
    for query in ["include_finals=true", "status=final&include_finals=true&limit=500", "competition=NBA&include_finals=true&limit=500"]:
        response = client.get(f"/games?{query}")
        assert response.headers["cache-control"] == "no-store"
        assert response.json()[0]["status"] == "final"
