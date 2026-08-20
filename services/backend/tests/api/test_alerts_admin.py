import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.db.models import Alert, AlertDelivery, Game, LeagueSetting, PushSubscription, Team, User
from app.db.session import SessionLocal
from app.routers.alerts import _build_admin_test_objects
from app.services import alert_delivery
from app.services.resend import ResendResult


SUPPORTED_TEST_ALERTS = {
    "NBA": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "WNBA": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "NFL": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "MLB": ("game_start", "inning_start", "extra_innings_start", "final_result"),
    "MLS": (
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    ),
    "WORLD_CUP": (
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    ),
}


def _auth_headers(
    client,
    *,
    email: str = "admin-alerts@example.com",
    role: str = "admin",
    delivery_mode: str = "email",
) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, role=role, alert_delivery_mode=delivery_mode)
            db.add(user)
        else:
            user.role = role
            user.alert_delivery_mode = delivery_mode
        db.commit()
        db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}
    finally:
        db.close()


def _sports_counts() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        return (
            db.scalar(select(func.count(Game.id))) or 0,
            db.scalar(select(func.count(Alert.id))) or 0,
            db.scalar(select(func.count(AlertDelivery.id))) or 0,
        )
    finally:
        db.close()


def test_admin_test_alert_requires_admin(client):
    headers = _auth_headers(client, role="user")
    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("league", "alert_type"),
    [(league, alert_type) for league, alert_types in SUPPORTED_TEST_ALERTS.items() for alert_type in alert_types],
)
def test_admin_test_alert_supports_every_league_alert_combination(client, league, alert_type):
    headers = _auth_headers(client, email=f"admin-{league.lower()}-{alert_type}@example.com")
    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": league, "alert_type": alert_type},
    )

    assert response.status_code == 200
    assert response.json() == {
        "league": league,
        "alert_type": alert_type,
        "deliveries": [
            {
                "channel": "email",
                "status": "sent",
                "attempted_at": response.json()["deliveries"][0]["attempted_at"],
            }
        ],
    }


@pytest.mark.parametrize(
    ("league", "alert_type", "expected"),
    [
        ("NBA", "overtime_start", ("in_progress", 112, 112, 5, "05:00")),
        ("NFL", "close_game_late", ("in_progress", 20, 17, 4, "04:30")),
        ("MLB", "extra_innings_start", ("in_progress", 3, 3, 10, "Top 10th")),
        ("MLS", "final_result", ("final", 2, 1, 2, "FT")),
    ],
)
def test_admin_test_scenarios_keep_representative_sport_state(client, league, alert_type, expected):
    _auth_headers(client)
    db = SessionLocal()
    try:
        away, home = db.scalars(
            select(Team).where(Team.league == league).order_by(Team.id.asc()).limit(2)
        ).all()
        game, _ = _build_admin_test_objects(
            user_id=1,
            league=league,
            alert_type=alert_type,
            away_team=away,
            home_team=home,
        )
    finally:
        db.close()

    assert (game.status, game.home_score, game.away_score, game.period, game.clock) == expected


def test_admin_test_alert_is_response_only(client):
    headers = _auth_headers(client)
    before = _sports_counts()

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "final_result"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"league", "alert_type", "deliveries"}
    assert _sports_counts() == before
    assert client.get("/alerts/history", headers=headers).json() == {"items": []}
    summary = client.get("/ops/admin/summary?window=24h", headers=headers).json()
    assert summary["overview"]["total_alerts_created"] == 0
    assert summary["delivery"]["email_alerts"] == {"attempted": 0, "sent": 0, "failed": 0}


def test_admin_test_alert_honors_both_delivery_mode(client):
    email = "admin-both@example.com"
    headers = _auth_headers(client, email=email, delivery_mode="both")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint="https://push.example/admin-test",
                p256dh="p" * 43,
                auth="a" * 22,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )

    assert response.status_code == 200
    assert [(row["channel"], row["status"]) for row in response.json()["deliveries"]] == [
        ("email", "sent"),
        ("push", "sent"),
    ]
    assert _sports_counts() == (0, 0, 0)


def test_admin_test_alert_returns_expected_delivery_failure(client, monkeypatch):
    headers = _auth_headers(client)
    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(
        alert_delivery,
        "send_resend_email",
        lambda **_kwargs: ResendResult(sent=False, metadata={"error": "provider_unavailable"}),
    )

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )

    assert response.status_code == 200
    assert response.json()["deliveries"][0]["status"] == "failed"
    assert _sports_counts() == (0, 0, 0)


def test_admin_test_push_commits_expired_subscription_cleanup(client, monkeypatch):
    email = "admin-expired-push@example.com"
    headers = _auth_headers(client, email=email, delivery_mode="push")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        subscription = PushSubscription(
            user_id=user.id,
            endpoint="https://push.example/expired-admin-test",
            p256dh="p" * 43,
            auth="a" * 22,
        )
        db.add(subscription)
        db.commit()
        subscription_id = subscription.id
    finally:
        db.close()

    class GoneResponse:
        status_code = 410

    def expired_push(**_kwargs):
        raise alert_delivery.WebPushException("gone", response=GoneResponse())

    monkeypatch.setattr(alert_delivery.delivery_settings, "delivery_mode", "live")
    monkeypatch.setattr(alert_delivery.delivery_settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(alert_delivery, "webpush", expired_push)

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )

    assert response.status_code == 200
    assert response.json()["deliveries"][0]["status"] == "failed"
    db = SessionLocal()
    try:
        assert db.get(PushSubscription, subscription_id) is None
    finally:
        db.close()


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"league": "UNKNOWN", "alert_type": "game_start"}, "Invalid league"),
        ({"league": "MLB", "alert_type": "close_game_late"}, "Invalid alert type"),
    ],
)
def test_admin_test_alert_rejects_invalid_requests(client, payload, detail):
    headers = _auth_headers(client)
    response = client.post("/alerts/admin/test", headers=headers, json=payload)
    assert response.status_code == 400
    assert detail in response.json()["detail"]


def test_admin_test_alert_rejects_disabled_league(client):
    headers = _auth_headers(client)
    db = SessionLocal()
    try:
        db.get(LeagueSetting, "MLB").is_enabled = False
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "MLB", "alert_type": "game_start"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "League is disabled"


def test_admin_test_alert_requires_two_seeded_teams(client):
    headers = _auth_headers(client)
    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).where(Team.league == "NBA").order_by(Team.id.asc())).all()
        for team in teams[1:]:
            db.delete(team)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Not enough teams available for test alerts"
