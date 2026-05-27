from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Game, SentAlert, User
from app.db.session import SessionLocal


def _auth_headers(client, email: str = "dev-alerts@example.com", role: str = "user") -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, role=role)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.role = role
            db.commit()
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_admin_test_email_endpoint_forbidden_for_non_admin(client):
    headers = _auth_headers(client, role="user")

    response = client.post(
        "/alerts/admin/test-email",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )
    assert response.status_code == 403


def test_admin_test_email_endpoint_creates_pending_alert(client):
    headers = _auth_headers(client, email="dev-alerts-on@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test-email",
        headers=headers,
        json={"league": "NBA", "alert_type": "final_result"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["game_id"], int)
    assert body["league"] == "NBA"
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
        game = db.get(Game, alerts[0].game_id)
        assert game is not None
        assert game.external_game_id.startswith("admin-test-game-")
        assert game.league == "NBA"
    finally:
        db.close()


def test_admin_test_email_endpoint_accepts_mlb_inning_start(client):
    headers = _auth_headers(client, email="dev-alerts-mlb@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test-email",
        headers=headers,
        json={"league": "MLB", "alert_type": "inning_start"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "MLB"
    assert body["alert_type"] == "inning_start"

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-mlb@example.com"))
        alerts = db.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
        assert len(alerts) == 1
        game = db.get(Game, alerts[0].game_id)
        assert game is not None
        assert game.league == "MLB"
    finally:
        db.close()


def test_admin_test_email_endpoint_rejects_invalid_league_alert_combo(client):
    headers = _auth_headers(client, email="dev-alerts-invalid@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test-email",
        headers=headers,
        json={"league": "MLB", "alert_type": "close_game_late"},
    )
    assert response.status_code == 400
    assert "Invalid alert type" in response.json()["detail"]
