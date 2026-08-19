from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Alert, AlertDelivery, Game, PushSubscription, User
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


def test_admin_test_alert_endpoint_forbidden_for_non_admin(client):
    headers = _auth_headers(client, role="user")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )
    assert response.status_code == 403


def test_admin_test_alert_endpoint_sends_inline_alert(client):
    headers = _auth_headers(client, email="dev-alerts-on@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "NBA", "alert_type": "final_result"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["game_id"], int)
    assert body["league"] == "NBA"
    assert body["alert_type"] == "final_result"
    assert body["deliveries"][0]["channel"] == "email"
    assert body["deliveries"][0]["status"] == "sent"

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-on@example.com"))
        alerts = db.scalars(select(Alert).where(Alert.user_id == user.id)).all()
        assert len(alerts) == 1
        delivery = db.scalar(select(AlertDelivery).where(AlertDelivery.alert_id == alerts[0].id))
        assert delivery is not None
        assert delivery.status == "sent"
        assert delivery.provider_message_id is not None
        assert alerts[0].alert_type == "final_result"
        assert alerts[0].event_data["source"] == "dev_test"
        game = db.get(Game, alerts[0].game_id)
        assert game is not None
        assert game.external_game_id.startswith("admin-test-game-")
        assert game.league == "NBA"
        assert game.is_test is True
    finally:
        db.close()


def test_admin_test_alert_endpoint_accepts_mlb_alerts(client):
    headers = _auth_headers(client, email="dev-alerts-mlb@example.com", role="admin")

    for alert_type in ("inning_start", "extra_innings_start"):
        response = client.post(
            "/alerts/admin/test",
            headers=headers,
            json={"league": "MLB", "alert_type": alert_type},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["league"] == "MLB"
        assert body["alert_type"] == alert_type

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-mlb@example.com"))
        alerts = db.scalars(select(Alert).where(Alert.user_id == user.id)).all()
        assert len(alerts) == 2
        extra_innings_alert = next(alert for alert in alerts if alert.alert_type == "extra_innings_start")
        game = db.get(Game, extra_innings_alert.game_id)
        assert game is not None
        assert (game.league, game.status, game.home_score, game.away_score) == ("MLB", "in_progress", 3, 3)
        assert (game.period, game.clock) == (10, "Top 10th")
    finally:
        db.close()


def test_admin_test_alert_endpoint_accepts_wnba_basketball_alerts(client):
    headers = _auth_headers(client, email="dev-alerts-wnba@example.com", role="admin")

    for alert_type in ("game_start", "close_game_late", "overtime_start", "final_result"):
        response = client.post(
            "/alerts/admin/test",
            headers=headers,
            json={"league": "WNBA", "alert_type": alert_type},
        )
        assert response.status_code == 200
        assert response.json()["league"] == "WNBA"
        assert response.json()["alert_type"] == alert_type

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-wnba@example.com"))
        overtime_alert = db.scalar(
            select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "overtime_start")
        )
        assert overtime_alert is not None
        overtime_game = db.get(Game, overtime_alert.game_id)
        assert overtime_game is not None
        assert (overtime_game.status, overtime_game.home_score, overtime_game.away_score) == ("in_progress", 112, 112)
        assert (overtime_game.period, overtime_game.clock) == (5, "05:00")
    finally:
        db.close()


def test_admin_test_alert_endpoint_accepts_nfl_football_alerts(client):
    headers = _auth_headers(client, email="dev-alerts-nfl@example.com", role="admin")

    for alert_type in ("game_start", "close_game_late", "overtime_start", "final_result"):
        response = client.post(
            "/alerts/admin/test",
            headers=headers,
            json={"league": "NFL", "alert_type": alert_type},
        )
        assert response.status_code == 200
        assert response.json()["league"] == "NFL"
        assert response.json()["alert_type"] == alert_type

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-nfl@example.com"))
        close_alert = db.scalar(
            select(Alert).where(Alert.user_id == user.id, Alert.alert_type == "close_game_late")
        )
        assert close_alert is not None
        close_game = db.get(Game, close_alert.game_id)
        assert close_game is not None
        assert (close_game.status, close_game.home_score, close_game.away_score) == (
            "in_progress",
            20,
            17,
        )
        assert (close_game.period, close_game.clock) == (4, "04:30")
    finally:
        db.close()


def test_admin_test_alert_endpoint_accepts_world_cup_game_start(client):
    headers = _auth_headers(client, email="dev-alerts-world-cup@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "WORLD_CUP", "alert_type": "game_start"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "WORLD_CUP"
    assert body["alert_type"] == "game_start"


def test_admin_test_alert_endpoint_accepts_world_cup_score_changed(client):
    headers = _auth_headers(client, email="dev-alerts-world-cup-score@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "WORLD_CUP", "alert_type": "score_changed"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "WORLD_CUP"
    assert body["alert_type"] == "score_changed"


def test_admin_test_alert_endpoint_accepts_world_cup_second_half_start(client):
    headers = _auth_headers(client, email="dev-alerts-world-cup-second-half@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "WORLD_CUP", "alert_type": "second_half_start"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "WORLD_CUP"
    assert body["alert_type"] == "second_half_start"


def test_admin_test_alert_endpoint_accepts_world_cup_extra_time_start(client):
    headers = _auth_headers(client, email="dev-alerts-world-cup-extra-time@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "WORLD_CUP", "alert_type": "extra_time_start"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "WORLD_CUP"
    assert body["alert_type"] == "extra_time_start"


def test_admin_test_alert_endpoint_accepts_world_cup_penalty_kicks(client):
    headers = _auth_headers(client, email="dev-alerts-world-cup-penalties@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "WORLD_CUP", "alert_type": "penalty_kicks"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["league"] == "WORLD_CUP"
    assert body["alert_type"] == "penalty_kicks"


def test_admin_test_alert_endpoint_accepts_mls_soccer_alerts(client):
    headers = _auth_headers(client, email="dev-alerts-mls@example.com", role="admin")

    for alert_type in (
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    ):
        response = client.post(
            "/alerts/admin/test",
            headers=headers,
            json={"league": "MLS", "alert_type": alert_type},
        )
        assert response.status_code == 200
        assert response.json()["league"] == "MLS"
        assert response.json()["alert_type"] == alert_type


def test_admin_test_alert_endpoint_rejects_invalid_league_alert_combo(client):
    headers = _auth_headers(client, email="dev-alerts-invalid@example.com", role="admin")

    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "MLB", "alert_type": "close_game_late"},
    )
    assert response.status_code == 400
    assert "Invalid alert type" in response.json()["detail"]


def test_admin_test_alert_endpoint_returns_final_delivery_status_immediately(client):
    headers = _auth_headers(client, email="dev-alerts-inline@example.com", role="admin")
    response = client.post(
        "/alerts/admin/test",
        headers=headers,
        json={"league": "MLB", "alert_type": "game_start"},
    )
    assert response.status_code == 200
    assert response.json()["deliveries"][0]["status"] == "sent"


def test_admin_test_alert_honors_both_delivery_mode(client):
    headers = _auth_headers(client, email="dev-alerts-both@example.com", role="admin")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "dev-alerts-both@example.com"))
        user.alert_delivery_mode = "both"
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


def test_old_admin_test_email_endpoint_is_removed(client):
    headers = _auth_headers(client, email="dev-alerts-old-route@example.com", role="admin")
    response = client.post(
        "/alerts/admin/test-email",
        headers=headers,
        json={"league": "NBA", "alert_type": "game_start"},
    )
    assert response.status_code == 404
