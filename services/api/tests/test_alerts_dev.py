from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.core.security import create_access_token
from app.db.models import Game, SentAlert, Team, User
from app.db.session import SessionLocal


def _auth_headers(client, email: str = "dev-alerts@example.com") -> dict[str, str]:
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


def _create_game(external_game_id: str) -> int:
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
        game = Game(
            external_game_id=external_game_id,
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime.now(timezone.utc),
            status="scheduled",
        )
        db.add(game)
        db.commit()
        db.refresh(game)
        return game.id
    finally:
        db.close()


def test_dev_test_email_endpoint_hidden_when_not_in_dev_mode(client, monkeypatch):
    headers = _auth_headers(client)
    monkeypatch.setattr(settings, "dev_mode", False)
    game_id = _create_game("dev-hidden-game")

    response = client.post(
        "/alerts/dev/test-email",
        headers=headers,
        json={"alert_type": "game_start", "game_id": game_id},
    )
    assert response.status_code == 404


def test_dev_test_email_endpoint_creates_pending_alert(client, monkeypatch):
    monkeypatch.setattr(settings, "dev_mode", True)
    headers = _auth_headers(client, email="dev-alerts-on@example.com")
    game_id = _create_game("dev-enabled-game")

    response = client.post(
        "/alerts/dev/test-email",
        headers=headers,
        json={"alert_type": "final_result", "game_id": game_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == game_id
    assert body["alert_type"] == "final_result"
    assert body["delivery_status"] == "pending"

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-on@example.com"))
        alerts = db.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
        assert len(alerts) == 1
        assert alerts[0].delivery_status == "pending"
        assert alerts[0].alert_type == "final_result"
        assert alerts[0].metadata_json["source"] == "dev_test"
    finally:
        db.close()
