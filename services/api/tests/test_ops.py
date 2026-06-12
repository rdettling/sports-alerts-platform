from datetime import datetime, timezone

from app.db.models import ApiCallRollupHourly, User, WorkerJob
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
    assert summary_json["expected_vs_actual"]["espn"]["expected"] == 0

    timeseries = client.get("/ops/api-usage/timeseries?window=24h&bucket=hour", headers=headers)
    assert timeseries.status_code == 200
    assert len(timeseries.json()["points"]) >= 2

    ingest_health = client.get("/ops/db/ingest-health?event_limit=10", headers=headers)
    assert ingest_health.status_code == 200
    assert len(ingest_health.json()["states"]) >= 1
    assert ingest_health.json()["active_leagues"] == ["NBA", "MLB"]

    league_settings = client.get("/ops/leagues", headers=headers)
    assert league_settings.status_code == 200
    assert league_settings.json()["items"] == [
        {"league": "NBA", "is_enabled": True},
        {"league": "MLB", "is_enabled": True},
    ]

    overview = client.get("/ops/admin/overview?window=24h&limit=10", headers=headers)
    assert overview.status_code == 200
    overview_json = overview.json()
    assert "global_health" in overview_json
    assert "providers" in overview_json
    assert "risk_cards" in overview_json
    assert len(overview_json["providers"]) >= 1


def test_team_mapping_health_endpoint(client, monkeypatch):
    token = _issue_token(client, monkeypatch, "ops-admin@example.com")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ops-admin@example.com").first()
        assert user is not None
        user.role = "admin"
        db.commit()
    finally:
        db.close()

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            _ = params
            if "mlb" in url:
                return _FakeResponse(
                    {
                        "events": [
                            {
                                "competitions": [
                                    {"competitors": [{"team": {"id": "2"}}, {"team": {"id": "10"}}]}
                                ]
                            }
                        ]
                    }
                )
            return _FakeResponse(
                {
                    "events": [
                        {
                            "competitions": [
                                {"competitors": [{"team": {"id": "1"}}, {"team": {"id": "2"}}]}
                            ]
                        }
                    ]
                }
            )

    monkeypatch.setattr("app.routers.ops.httpx.Client", _FakeClient)

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/ops/db/team-mapping-health?date=20260528", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert len(payload["leagues"]) == 2
    assert payload["leagues"][0]["missing_team_ids"] == []
    assert payload["leagues"][1]["missing_team_ids"] == []
