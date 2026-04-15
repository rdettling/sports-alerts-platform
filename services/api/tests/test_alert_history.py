from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Game, SentAlert, Team, User
from app.db.session import SessionLocal


def _auth_headers(client, email: str = "history@example.com") -> dict[str, str]:
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


def test_alert_history_filters_by_type_and_time(client):
    headers = _auth_headers(client, email="history-filters@example.com")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "history-filters@example.com"))
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id="history-game-filters",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc),
            status="final",
        )
        db.add(game)
        db.commit()
        db.refresh(game)

        old_alert = SentAlert(
            user_id=user.id,
            game_id=game.id,
            alert_type="game_start",
            delivery_channel="email",
            delivery_status="sent",
            dedupe_key=f"{user.id}:{game.id}:game_start:old",
            sent_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        recent_alert = SentAlert(
            user_id=user.id,
            game_id=game.id,
            alert_type="final_result",
            delivery_channel="email",
            delivery_status="sent",
            dedupe_key=f"{user.id}:{game.id}:final_result:recent",
            sent_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add_all([old_alert, recent_alert])
        db.commit()
    finally:
        db.close()

    by_type = client.get("/alerts/history?alert_type=final_result", headers=headers)
    assert by_type.status_code == 200
    assert len(by_type.json()["items"]) == 1
    assert by_type.json()["items"][0]["alert_type"] == "final_result"

    by_time = client.get("/alerts/history?since_hours=24", headers=headers)
    assert by_time.status_code == 200
    assert len(by_time.json()["items"]) == 1
    assert by_time.json()["items"][0]["alert_type"] == "final_result"
