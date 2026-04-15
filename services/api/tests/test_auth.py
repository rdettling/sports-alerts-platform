from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db.models import EmailLoginToken
from app.db.session import SessionLocal


def _issue_token_via_start(client, monkeypatch, email: str, token: str = "known-magic-link-token-for-tests-12345") -> str:
    monkeypatch.setattr("app.routers.auth.secrets.token_urlsafe", lambda _: token)
    response = client.post("/auth/magic-link/start", json={"email": email})
    assert response.status_code == 200
    body = response.json()
    assert body["message"]
    return token


def _auth_headers(client, monkeypatch, email: str = "user@example.com") -> dict[str, str]:
    token = _issue_token_via_start(client, monkeypatch, email)
    verify = client.post("/auth/magic-link/verify", json={"token": token})
    assert verify.status_code == 200
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_magic_link_start_verify_and_me_flow(client, monkeypatch):
    token = _issue_token_via_start(client, monkeypatch, "user@example.com")

    verify_response = client.post("/auth/magic-link/verify", json={"token": token})
    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert "access_token" in verify_data
    assert verify_data["user"]["email"] == "user@example.com"

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {verify_data['access_token']}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_magic_link_start_always_returns_neutral_message_for_unknown_email(client):
    response = client.post("/auth/magic-link/start", json={"email": "unknown@example.com"})
    assert response.status_code == 200
    assert response.json()["message"] == "If that email can receive login links, one has been sent."


def test_magic_link_is_one_time_use(client, monkeypatch):
    token = _issue_token_via_start(client, monkeypatch, "onetime@example.com")
    first = client.post("/auth/magic-link/verify", json={"token": token})
    second = client.post("/auth/magic-link/verify", json={"token": token})
    assert first.status_code == 200
    assert second.status_code == 401


def test_magic_link_verify_fails_when_expired(client, monkeypatch):
    token = _issue_token_via_start(client, monkeypatch, "expired@example.com")
    db = SessionLocal()
    try:
        token_row = db.query(EmailLoginToken).filter(EmailLoginToken.consumed_at.is_(None)).first()
        assert token_row is not None
        token_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/magic-link/verify", json={"token": token})
    assert response.status_code == 401


def test_magic_link_start_enforces_cooldown_and_hourly_rate_cap(client):
    first = client.post("/auth/magic-link/start", json={"email": "limits@example.com"})
    second = client.post("/auth/magic-link/start", json={"email": "limits@example.com"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["message"] == second.json()["message"]
    assert "dev_magic_link" not in second.json()

    db = SessionLocal()
    try:
        rows = db.query(EmailLoginToken).filter(EmailLoginToken.email == "limits@example.com").all()
        assert len(rows) == 1
        rows[0].created_at = datetime.now(timezone.utc) - timedelta(seconds=settings.magic_link_cooldown_seconds + 1)
        db.commit()
    finally:
        db.close()

    for _ in range(settings.magic_link_max_requests_per_hour - 1):
        response = client.post("/auth/magic-link/start", json={"email": "limits@example.com"})
        assert response.status_code == 200
        db = SessionLocal()
        try:
            latest = (
                db.query(EmailLoginToken)
                .filter(EmailLoginToken.email == "limits@example.com")
                .order_by(EmailLoginToken.created_at.desc())
                .first()
            )
            assert latest is not None
            latest.created_at = datetime.now(timezone.utc) - timedelta(seconds=settings.magic_link_cooldown_seconds + 1)
            db.commit()
        finally:
            db.close()

    capped = client.post("/auth/magic-link/start", json={"email": "limits@example.com"})
    assert capped.status_code == 200
    assert "dev_magic_link" not in capped.json()


def test_magic_link_start_has_no_dev_link_in_response(client):
    response = client.post("/auth/magic-link/start", json={"email": "nodev@example.com"})
    assert response.status_code == 200
    assert "dev_magic_link" not in response.json()


def test_magic_link_start_validation_error_returns_readable_detail(client):
    response = client.post("/auth/magic-link/start", json={"email": "not-an-email"})
    assert response.status_code == 422
    assert isinstance(response.json().get("detail"), str)
