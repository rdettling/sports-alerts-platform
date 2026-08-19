from datetime import datetime, timezone

from app.db.models import Alert, AlertDelivery, ApiCallRollupHourly, User, WorkerJob
from app.db.session import SessionLocal


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
        db.add(WorkerJob(job_type="catalog_sync", status="queued", next_run_at=now, max_attempts=5))
        db.add(WorkerJob(job_type="live_sync", status="queued", next_run_at=now, max_attempts=5))
        db.add(
            ApiCallRollupHourly(
                bucket_start=now,
                service="worker",
                provider="espn",
                endpoint_key="scoreboard",
                attempt_status="success",
                call_count=3,
            )
        )
        db.add(
            ApiCallRollupHourly(
                bucket_start=now,
                service="worker",
                provider="the_odds_api",
                endpoint_key="h2h",
                attempt_status="success",
                call_count=2,
            )
        )
        db.add(
            ApiCallRollupHourly(
                bucket_start=now,
                service="worker",
                provider="odds",
                endpoint_key="h2h",
                attempt_status="rate_limited",
                call_count=1,
            )
        )
        db.add(
            ApiCallRollupHourly(
                bucket_start=now,
                service="worker",
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="success",
                call_count=2,
            )
        )
        db.add(
            ApiCallRollupHourly(
                bucket_start=now,
                service="api",
                provider="resend",
                endpoint_key="resend_send_email",
                attempt_status="error",
                call_count=1,
            )
        )
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
                    )
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
    assert summary_json["overview"]["total_provider_calls"] == 9
    assert summary_json["overview"]["provider_errors"] == 1
    assert summary_json["overview"]["provider_rate_limits"] == 1
    assert summary_json["overview"]["total_emails_attempted"] == 3
    assert summary_json["overview"]["emails_sent"] == 2
    assert summary_json["overview"]["emails_failed"] == 1
    assert summary_json["overview"]["total_alerts_created"] == 2
    assert [item["provider"] for item in summary_json["providers"]] == ["espn", "odds", "resend"]
    assert summary_json["providers"][1]["total_calls"] == 3
    assert summary_json["providers"][1]["most_used_endpoint"] == "h2h"
    assert summary_json["delivery"]["email_alerts"] == {"attempted": 2, "sent": 1, "failed": 1}
    assert summary_json["delivery"]["push_alerts"] == {"attempted": 0, "sent": 0, "failed": 0}
    assert summary_json["delivery"]["magic_links"] == {"attempted": 1, "sent": 1, "failed": 0}
    assert summary_json["delivery"]["resend"] == {
        "total_calls": 3,
        "success_calls": 2,
        "error_calls": 1,
        "rate_limited_calls": 0,
    }
    assert summary_json["runtime"]["active_leagues"] == ["NBA", "WNBA", "NFL", "MLB", "MLS", "WORLD_CUP"]
    assert len(summary_json["runtime"]["league_settings"]) == 6

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

    league_update = client.put(
        "/ops/leagues/MLB",
        headers=headers,
        json={"is_enabled": False},
    )
    assert league_update.status_code == 200
    assert league_update.json()["league"] == "MLB"
    assert league_update.json()["is_enabled"] is False
