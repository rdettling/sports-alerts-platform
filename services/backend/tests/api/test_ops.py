from datetime import datetime, timezone

from app.db.models import Alert, AlertDelivery, User
from app.db.session import SessionLocal
from app.schemas.schedule import ScheduleSnapshot
from app.services import worker_schedule


def _issue_token(client, monkeypatch, email: str) -> str:
    monkeypatch.setattr("app.routers.auth.secrets.token_urlsafe", lambda _: f"token-{email}-for-tests-123456")
    start = client.post("/auth/magic-link/start", json={"email": email})
    assert start.status_code == 200
    verify = client.post("/auth/magic-link/verify", json={"token": f"token-{email}-for-tests-123456"})
    assert verify.status_code == 200
    return verify.json()["access_token"]


def test_ops_routes_require_admin(client, monkeypatch):
    token = _issue_token(client, monkeypatch, "regular@example.com")

    response = client.get("/ops/admin/summary?window=24h", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_ops_routes_return_data_for_admin(client, monkeypatch):
    token = _issue_token(client, monkeypatch, "admin@example.com")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        assert user is not None
        user.role = "admin"
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        db.add(
            Alert(
                user_id=user.id,
                game_id=1,
                alert_type="game_start",
                event_key="alert-1",
                triggered_at=now,
                deliveries=[
                    AlertDelivery(
                        channel="email",
                        status="sent",
                        provider_message_id="msg-1",
                        attempted_at=now,
                    ),
                    AlertDelivery(channel="push", status="failed", attempted_at=now),
                ],
            )
        )
        db.add(
            Alert(
                user_id=user.id,
                game_id=1,
                alert_type="final_result",
                event_key="alert-2",
                triggered_at=now,
                deliveries=[AlertDelivery(channel="email", status="failed", attempted_at=now)],
            )
        )
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/ops/admin/summary?window=24h", headers=headers)
    assert summary.status_code == 200
    summary_json = summary.json()
    assert set(summary_json) == {"overview", "delivery", "competition_settings", "schedule"}
    assert summary_json["schedule"] is None
    worker_schedule.snapshot = ScheduleSnapshot(reported_at=now, next_catalog_at=now, jobs=[])
    assert client.get("/ops/admin/summary", headers=headers).json()["schedule"] == worker_schedule.snapshot.model_dump(mode="json")
    assert set(summary_json["overview"]) == {"window", "total_alerts_created", "last_updated_at"}
    assert set(summary_json["delivery"]) == {"email_alerts", "push_alerts"}
    assert summary_json["overview"]["total_alerts_created"] == 2
    assert summary_json["delivery"]["email_alerts"] == {"attempted": 2, "sent": 1, "failed": 1}
    assert summary_json["delivery"]["push_alerts"] == {"attempted": 1, "sent": 0, "failed": 1}
    assert [item["competition"] for item in summary_json["competition_settings"]] == [
        "NBA",
        "WNBA",
        "NFL",
        "FBS",
        "MLB",
        "MLS",
        "LA_LIGA",
        "PREMIER_LEAGUE",
        "WORLD_CUP",
    ]
    assert "runtime" not in summary_json
    assert client.get("/ops/admin/summary?window=bad", headers=headers).status_code == 422

    monkeypatch.setattr("app.routers.ops.settings.neon_api_key", "")
    neon_usage = client.get("/ops/db/neon-usage", headers=headers)
    assert neon_usage.status_code == 200
    assert neon_usage.json() == {
        "available": False,
        "project_id": None,
        "project_name": None,
        "dashboard_url": None,
        "consumption_period_start": None,
        "consumption_period_end": None,
        "cpu_used_sec": None,
        "active_time_sec": None,
        "compute_last_active_at": None,
        "avg_cu_while_active": None,
        "message": "NEON_API_KEY is not configured.",
    }

    competition_update = client.put(
        "/ops/competitions/MLB",
        headers=headers,
        json={"is_enabled": False},
    )
    assert competition_update.status_code == 200
    assert competition_update.json()["competition"] == "MLB"
    assert competition_update.json()["is_enabled"] is False
    refreshed_summary = client.get("/ops/admin/summary?window=24h", headers=headers).json()
    refreshed_mlb = next(
        item
        for item in refreshed_summary["competition_settings"]
        if item["competition"] == "MLB"
    )
    assert refreshed_mlb["is_enabled"] is False
