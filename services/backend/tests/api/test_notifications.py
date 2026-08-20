from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import PushSubscription, User
from app.db.session import SessionLocal


def _auth_headers(email: str) -> tuple[dict[str, str], int]:
    db = SessionLocal()
    try:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}, user.id
    finally:
        db.close()


def _subscription(endpoint: str) -> dict:
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "p" * 43,
            "auth": "a" * 22,
        },
    }


def test_notification_settings_default_to_email_and_hide_subscription_secrets(client):
    headers, _ = _auth_headers("settings@example.com")

    response = client.get("/notification-settings", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "email_alerts_enabled": True,
        "push_subscription_count": 0,
        "push_configured": True,
        "vapid_public_key": "test-public-key",
    }


def test_email_setting_is_independent_from_push_subscriptions(client):
    headers, user_id = _auth_headers("preference@example.com")
    assert (
        client.post(
            "/push-subscriptions",
            headers=headers,
            json=_subscription("https://push.example/subscription-1"),
        ).status_code
        == 204
    )
    disabled = client.put(
        "/notification-settings",
        headers=headers,
        json={"email_alerts_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["email_alerts_enabled"] is False
    assert disabled.json()["push_subscription_count"] == 1

    enabled = client.put(
        "/notification-settings",
        headers=headers,
        json={"email_alerts_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["email_alerts_enabled"] is True
    assert enabled.json()["push_subscription_count"] == 1

    db = SessionLocal()
    try:
        assert db.scalar(select(PushSubscription).where(PushSubscription.user_id == user_id)) is not None
    finally:
        db.close()


def test_notification_settings_reject_legacy_delivery_mode(client):
    headers, _ = _auth_headers("invalid-mode@example.com")
    response = client.put(
        "/notification-settings",
        headers=headers,
        json={"delivery_mode": "push"},
    )
    assert response.status_code == 422


def test_subscription_status_is_scoped_to_current_user(client):
    first_headers, _ = _auth_headers("status-first@example.com")
    second_headers, _ = _auth_headers("status-second@example.com")
    endpoint = "https://push.example/status"
    client.post("/push-subscriptions", headers=first_headers, json=_subscription(endpoint))

    first = client.post(
        "/push-subscriptions/status",
        headers=first_headers,
        json={"endpoint": endpoint},
    )
    second = client.post(
        "/push-subscriptions/status",
        headers=second_headers,
        json={"endpoint": endpoint},
    )

    assert first.status_code == 200
    assert first.json() == {"is_subscribed": True}
    assert second.status_code == 200
    assert second.json() == {"is_subscribed": False}


def test_subscription_registration_is_idempotent_and_reassigns_endpoint(client):
    first_headers, first_user_id = _auth_headers("first-push@example.com")
    second_headers, second_user_id = _auth_headers("second-push@example.com")
    endpoint = "https://push.example/shared"

    client.post("/push-subscriptions", headers=first_headers, json=_subscription(endpoint))
    updated = _subscription(endpoint)
    updated["keys"]["auth"] = "b" * 22
    client.post("/push-subscriptions", headers=first_headers, json=updated)
    client.post("/push-subscriptions", headers=second_headers, json=updated)

    db = SessionLocal()
    try:
        subscriptions = db.scalars(select(PushSubscription)).all()
        assert len(subscriptions) == 1
        assert subscriptions[0].user_id == second_user_id
        assert subscriptions[0].user_id != first_user_id
        assert subscriptions[0].auth == "b" * 22
    finally:
        db.close()


def test_subscription_delete_is_scoped_to_current_user(client):
    first_headers, _ = _auth_headers("delete-first@example.com")
    second_headers, second_user_id = _auth_headers("delete-second@example.com")
    endpoint = "https://push.example/delete"
    client.post("/push-subscriptions", headers=second_headers, json=_subscription(endpoint))

    assert (
        client.request(
            "DELETE",
            "/push-subscriptions",
            headers=first_headers,
            json={"endpoint": endpoint},
        ).status_code
        == 204
    )

    db = SessionLocal()
    try:
        assert db.scalar(
            select(PushSubscription).where(PushSubscription.user_id == second_user_id)
        ) is not None
    finally:
        db.close()
