from datetime import datetime, timedelta, timezone
from time import monotonic

from app.config import settings
from app.db.models import EmailLoginToken
from app.db.session import SessionLocal
from app.services import sign_in_delivery
from app.services.resend import ResendResult
from app.services.sign_in_email import build_sign_in_email

TEST_CODE = "123456"


def _issue_token_via_start(
    client,
    monkeypatch,
    email: str,
    token: str = "known-magic-link-token-for-tests-12345",
    code: str = TEST_CODE,
) -> str:
    monkeypatch.setattr("app.routers.auth.secrets.token_urlsafe", lambda _: token)
    monkeypatch.setattr("app.routers.auth.secrets.randbelow", lambda _: int(code))
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
    assert verify_data["user"]["role"] == "user"

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {verify_data['access_token']}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"
    assert me_response.json()["role"] == "user"


def test_magic_code_start_verify_and_me_flow(client, monkeypatch):
    _issue_token_via_start(client, monkeypatch, "code-user@example.com")

    verify_response = client.post(
        "/auth/magic-code/verify",
        json={"email": " CODE-user@example.com ", "code": TEST_CODE},
    )
    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert verify_data["user"]["email"] == "code-user@example.com"

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {verify_data['access_token']}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "code-user@example.com"


def test_magic_link_and_code_are_one_shared_challenge(client, monkeypatch):
    link_token = _issue_token_via_start(client, monkeypatch, "link-first@example.com")
    assert client.post("/auth/magic-link/verify", json={"token": link_token}).status_code == 200
    code_after_link = client.post(
        "/auth/magic-code/verify",
        json={"email": "link-first@example.com", "code": TEST_CODE},
    )
    assert code_after_link.status_code == 401

    code_token = _issue_token_via_start(
        client,
        monkeypatch,
        "code-first@example.com",
        token="second-magic-link-token-for-tests-12345",
    )
    assert (
        client.post(
            "/auth/magic-code/verify",
            json={"email": "code-first@example.com", "code": TEST_CODE},
        ).status_code
        == 200
    )
    assert client.post("/auth/magic-link/verify", json={"token": code_token}).status_code == 401


def test_magic_code_attempt_limit_does_not_disable_link(client, monkeypatch):
    token = _issue_token_via_start(client, monkeypatch, "attempts@example.com")

    for _ in range(5):
        response = client.post(
            "/auth/magic-code/verify",
            json={"email": "attempts@example.com", "code": "000000"},
        )
        assert response.status_code == 401

    locked = client.post(
        "/auth/magic-code/verify",
        json={"email": "attempts@example.com", "code": TEST_CODE},
    )
    assert locked.status_code == 401
    assert client.post("/auth/magic-link/verify", json={"token": token}).status_code == 200


def test_new_magic_link_invalidates_older_challenge(client, monkeypatch):
    old_token = _issue_token_via_start(
        client,
        monkeypatch,
        "newest@example.com",
        token="old-magic-link-token-for-tests-123456",
        code="111111",
    )
    db = SessionLocal()
    try:
        old_row = db.query(EmailLoginToken).filter(EmailLoginToken.email == "newest@example.com").one()
        old_row.created_at = datetime.now(timezone.utc) - timedelta(
            seconds=settings.magic_link_cooldown_seconds + 1
        )
        db.commit()
    finally:
        db.close()

    _issue_token_via_start(
        client,
        monkeypatch,
        "newest@example.com",
        token="new-magic-link-token-for-tests-123456",
        code="222222",
    )

    assert client.post("/auth/magic-link/verify", json={"token": old_token}).status_code == 401
    old_code = client.post(
        "/auth/magic-code/verify",
        json={"email": "newest@example.com", "code": "111111"},
    )
    assert old_code.status_code == 401
    new_code = client.post(
        "/auth/magic-code/verify",
        json={"email": "newest@example.com", "code": "222222"},
    )
    assert new_code.status_code == 200


def test_magic_code_is_hashed_and_expiration_is_enforced(client, monkeypatch):
    _issue_token_via_start(client, monkeypatch, "expired-code@example.com")
    db = SessionLocal()
    try:
        token_row = db.query(EmailLoginToken).filter(EmailLoginToken.email == "expired-code@example.com").one()
        assert token_row.code_hash != TEST_CODE
        assert len(token_row.code_hash) == 64
        token_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/magic-code/verify",
        json={"email": "expired-code@example.com", "code": TEST_CODE},
    )
    assert response.status_code == 401


def test_magic_code_requires_exactly_six_digits(client):
    for code in ("12345", "1234567", "12A456"):
        response = client.post(
            "/auth/magic-code/verify",
            json={"email": "user@example.com", "code": code},
        )
        assert response.status_code == 422


def test_sign_in_email_contains_link_code_expiry_and_home_screen_guidance():
    subject, text_body, html_body = build_sign_in_email(
        "https://example.com/auth?token=secret",
        TEST_CODE,
        15,
    )

    assert subject == "Sign in to Live Game Alerts"
    for body in (text_body, html_body):
        assert TEST_CODE in body
        assert "https://example.com/auth?token=secret" in body
        assert "15 minutes" in body
        assert "Home Screen app" in body


def test_sign_in_email_live_failure_is_swallowed(monkeypatch, caplog):
    monkeypatch.setattr(sign_in_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(
        sign_in_delivery,
        "send_resend_email",
        lambda *args, **kwargs: ResendResult(
            sent=False,
            metadata={"error": "resend_http_error", "detail": "network unavailable"},
        ),
    )

    sign_in_delivery.send_sign_in_email(
        "user@example.com",
        "https://example.com/auth?token=secret",
        TEST_CODE,
    )

    assert "network unavailable" in caplog.text


def test_magic_link_start_always_returns_neutral_message_for_unknown_email(client):
    response = client.post("/auth/magic-link/start", json={"email": "unknown@example.com"})
    assert response.status_code == 200
    assert response.json()["message"] == "If that address can receive email, sign-in instructions have been sent."


def test_auth_warm_returns_204(client):
    response = client.post("/auth/warm")
    assert response.status_code == 204
    assert response.text == ""


def test_auth_warm_failure_is_fast(client, monkeypatch):
    def fail_warm(_db):
        raise RuntimeError("simulated timeout")

    monkeypatch.setattr("app.routers.auth._run_warm_query", fail_warm)
    started = monotonic()
    response = client.post("/auth/warm")
    elapsed = monotonic() - started
    assert response.status_code == 503
    assert response.json()["detail"] == "Database warmup failed"
    assert elapsed < 1.0


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
