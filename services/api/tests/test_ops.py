from datetime import datetime, timezone

from app.db.models import ApiCallRollupHourly, IngestRun, User
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

    response = client.get("/ops/api-usage/summary?window=24h", headers={"Authorization": f"Bearer {token}"})
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
            IngestRun(
                status="success",
                started_at=now,
                completed_at=now,
                expected_espn_calls=3,
                actual_espn_calls=3,
                expected_odds_calls=1,
                actual_odds_calls=1,
                poll_mode="live",
            )
        )
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
                provider="odds",
                endpoint_key="h2h",
                attempt_status="rate_limited",
                call_count=1,
            )
        )
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/ops/api-usage/summary?window=24h", headers=headers)
    assert summary.status_code == 200
    summary_json = summary.json()
    assert summary_json["totals"]["actual_calls"] == 4
    assert summary_json["expected_vs_actual"]["espn"]["expected"] == 3

    timeseries = client.get("/ops/api-usage/timeseries?window=24h&bucket=hour", headers=headers)
    assert timeseries.status_code == 200
    assert len(timeseries.json()["points"]) >= 2

    ingest_runs = client.get("/ops/api-usage/ingest-runs?limit=10", headers=headers)
    assert ingest_runs.status_code == 200
    assert len(ingest_runs.json()["items"]) >= 1
