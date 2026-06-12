from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import ApiCallRollupHourly, Game, SentAlert, Team, User
from app.services.email_branding import APP_BRAND_NAME
from worker import delivery
from worker.delivery import process_pending_alerts


def _seed_pending_alert(db_session) -> SentAlert:
    user = User(email="delivery@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id="delivery-game",
        league="NBA",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=101,
        away_score=99,
    )
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)

    alert = SentAlert(
        user_id=user.id,
        game_id=game.id,
        alert_type="game_start",
        delivery_channel="email",
        delivery_status="pending",
        dedupe_key=f"{user.id}:{game.id}:game_start",
        metadata_json={"status": "in_progress"},
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_email_delivery_success_marks_sent(db_session, monkeypatch):
    alert = _seed_pending_alert(db_session)

    def fake_post(url, json, headers, timeout):
        class Response:
            is_success = True
            status_code = 200
            text = '{"id":"email_123"}'

            @staticmethod
            def json():
                return {"id": "email_123"}

        assert "api.resend.com" in url
        assert json["to"] == ["delivery@example.com"]
        assert json["subject"].startswith("Tip-off ·")
        assert "html" in json
        assert APP_BRAND_NAME in json["html"]
        assert "text" in json
        assert "Bearer test-key" in headers["Authorization"]
        assert timeout == 15.0
        return Response()

    monkeypatch.setattr(delivery.settings, "delivery_mode", "email")
    monkeypatch.setattr(delivery.settings, "resend_api_key", "test-key")
    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    sent_count, failed_count = process_pending_alerts(db_session)
    assert sent_count == 1
    assert failed_count == 0

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "sent"
    assert updated.provider_message_id == "email_123"
    assert updated.metadata_json == {"status": "in_progress"}
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "success"


def test_email_delivery_failure_marks_failed_and_keeps_metadata(db_session, monkeypatch):
    alert = _seed_pending_alert(db_session)

    def fake_post(url, json, headers, timeout):
        class Response:
            is_success = False
            status_code = 401
            text = "unauthorized"

            @staticmethod
            def json():
                return {"message": "unauthorized"}

        return Response()

    monkeypatch.setattr(delivery.settings, "delivery_mode", "email")
    monkeypatch.setattr(delivery.settings, "resend_api_key", "bad-key")
    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    sent_count, failed_count = process_pending_alerts(db_session)
    assert sent_count == 0
    assert failed_count == 1

    updated = db_session.get(SentAlert, alert.id)
    assert updated is not None
    assert updated.delivery_status == "failed"
    assert updated.metadata_json is not None
    assert updated.metadata_json["status"] == "in_progress"
    assert updated.metadata_json["error"] == "resend_request_failed"
    assert updated.metadata_json["status_code"] == 401
    resend_rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "resend")).all()
    assert len(resend_rollups) == 1
    assert resend_rollups[0].attempt_status == "error"


def test_score_changed_delivery_uses_metadata_scores_for_subject(db_session, monkeypatch):
    user = User(email="score-changed@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()).limit(2)).all()
    game = Game(
        external_game_id="delivery-world-cup-game",
        league="WORLD_CUP",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc),
        status="in_progress",
        home_score=2,
        away_score=2,
        period=2,
        clock="70'",
    )
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)

    alert = SentAlert(
        user_id=user.id,
        game_id=game.id,
        alert_type="score_changed",
        delivery_channel="email",
        delivery_status="pending",
        dedupe_key=f"{user.id}:{game.id}:score_changed:2-2",
        metadata_json={
            "status": "in_progress",
            "period": 2,
            "clock": "68'",
            "previous_home_score": 1,
            "previous_away_score": 1,
            "new_home_score": 2,
            "new_away_score": 2,
            "scoring_side": None,
            "is_inferred_goal": False,
        },
    )
    db_session.add(alert)
    db_session.commit()

    def fake_post(url, json, headers, timeout):
        class Response:
            is_success = True
            status_code = 200
            text = '{"id":"email_456"}'

            @staticmethod
            def json():
                return {"id": "email_456"}

        assert json["subject"] == "Score update · USA 2–2 MEX"
        assert "Score update · USA 2–2 MEX" in json["text"]
        assert "68'" in json["text"]
        return Response()

    monkeypatch.setattr(delivery.settings, "delivery_mode", "email")
    monkeypatch.setattr(delivery.settings, "resend_api_key", "test-key")
    monkeypatch.setattr(delivery.httpx, "post", fake_post)

    sent_count, failed_count = process_pending_alerts(db_session)
    assert sent_count == 1
    assert failed_count == 0
