from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Game, SentAlert, Team, User
from app.db.session import SessionLocal


def _auth_headers(client, email: str = "history@example.com") -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "password123"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_alert_history_returns_sent_alert_rows(client):
    headers = _auth_headers(client)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "history@example.com"))
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id="history-game",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc),
            status="in_progress",
        )
        db.add(game)
        db.commit()
        db.refresh(game)

        db.add(
            SentAlert(
                user_id=user.id,
                game_id=game.id,
                alert_type="game_start",
                delivery_channel="email",
                delivery_status="sent",
                dedupe_key=f"{user.id}:{game.id}:game_start",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/alerts/history", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["alert_type"] == "game_start"
    assert item["delivery_status"] == "sent"
    assert item["home_team_abbreviation"]
    assert item["away_team_abbreviation"]
