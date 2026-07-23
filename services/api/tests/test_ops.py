from datetime import datetime, timezone

from app.db.models import ApiCallRollupHourly, SentAlert, User, WorkerJob
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
            SentAlert(
                user_id=user.id,
                game_id=1,
                alert_type="game_start",
                delivery_channel="email",
                delivery_status="sent",
                dedupe_key="sent-alert-1",
                provider_message_id="msg-1",
                sent_at=now,
            )
        )
        db.add(
            SentAlert(
                user_id=user.id,
                game_id=1,
                alert_type="final_result",
                delivery_channel="email",
                delivery_status="failed",
                dedupe_key="sent-alert-2",
                sent_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/ops/api-usage/summary?window=24h", headers=headers)
    assert summary.status_code == 200
    summary_json = summary.json()
    assert summary_json["totals"]["actual_calls"] == 9
    assert summary_json["expected_vs_actual"]["espn"]["expected"] == 0

    timeseries = client.get("/ops/api-usage/timeseries?window=24h&bucket=hour", headers=headers)
    assert timeseries.status_code == 200
    assert len(timeseries.json()["points"]) >= 2

    ingest_health = client.get("/ops/db/ingest-health?event_limit=10", headers=headers)
    assert ingest_health.status_code == 200
    assert len(ingest_health.json()["states"]) >= 1
    assert ingest_health.json()["active_leagues"] == ["NBA", "MLB", "WORLD_CUP"]

    league_settings = client.get("/ops/leagues", headers=headers)
    assert league_settings.status_code == 200
    assert league_settings.json()["items"] == [
        {"league": "NBA", "sport": "basketball", "label": "NBA", "badge_label": "NBA", "alert_types": ["game_start", "close_game_late", "final_result"], "live_sync_interval_seconds": 120, "default_test_matchup": ["ATL", "BOS"], "is_enabled": True},
        {"league": "MLB", "sport": "baseball", "label": "MLB", "badge_label": "MLB", "alert_types": ["game_start", "inning_start", "final_result"], "live_sync_interval_seconds": 300, "default_test_matchup": ["MIA", "TOR"], "is_enabled": True},
        {"league": "WORLD_CUP", "sport": "soccer", "label": "World Cup", "badge_label": "WC", "alert_types": ["game_start", "second_half_start", "extra_time_start", "penalty_kicks", "score_changed", "final_result"], "live_sync_interval_seconds": 180, "default_test_matchup": ["MEX", "USA"], "is_enabled": True},
    ]

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
    assert summary_json["delivery"]["alerts"] == {"attempted": 2, "sent": 1, "failed": 1}
    assert summary_json["delivery"]["magic_links"] == {"attempted": 1, "sent": 1, "failed": 0}
    assert summary_json["delivery"]["resend"] == {
        "total_calls": 3,
        "success_calls": 2,
        "error_calls": 1,
        "rate_limited_calls": 0,
    }
    assert summary_json["runtime"]["active_leagues"] == ["NBA", "MLB", "WORLD_CUP"]
    assert len(summary_json["runtime"]["league_settings"]) == 3


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
            if "fifa.world" in url:
                return _FakeResponse(
                    {
                        "events": [
                            {
                                "competitions": [
                                    {"competitors": [{"team": {"id": "203"}}, {"team": {"id": "660"}}]}
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
    assert len(payload["leagues"]) == 3
    assert payload["leagues"][0]["missing_team_ids"] == []
    assert payload["leagues"][1]["missing_team_ids"] == []
    assert payload["leagues"][2]["missing_team_ids"] == []
