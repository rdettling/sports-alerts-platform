from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, Team
from app.db.session import SessionLocal


def _create_game() -> Game:
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id="test-odds-game",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
            status="scheduled",
            is_final=False,
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        return game
    finally:
        db.close()


def test_games_include_odds_when_available(client):
    game = _create_game()
    db = SessionLocal()
    try:
        db.add(
            GameOddsCurrent(
                game_id=game.id,
                provider="the_odds_api",
                market="h2h",
                home_moneyline=-145,
                away_moneyline=125,
                bookmaker="DraftKings",
                fetched_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/games")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["odds"]["home_moneyline"] == -145
    assert payload[0]["odds"]["away_moneyline"] == 125
    assert payload[0]["odds"]["bookmaker"] == "DraftKings"


def test_games_skip_odds_fetch_when_include_odds_is_false(client):
    _create_game()
    response = client.get("/games?include_odds=false")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["odds"] is None
