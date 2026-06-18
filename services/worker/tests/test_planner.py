from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, Team
from worker.planner import build_catalog_requests, build_fetch_plan, build_live_requests


def _seed_game(db_session, *, external_id: str, status: str, scheduled_start: datetime, is_final: bool = False) -> None:
    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id=external_id,
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=scheduled_start,
            status=status,
            is_final=is_final,
        )
    )
    db_session.commit()


def test_planner_live_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-live", status="in_progress", scheduled_start=now)
    plan = build_fetch_plan(db_session, "NBA", now=now)

    assert plan.mode == "live"
    assert plan.next_ingest_seconds == 120
    assert plan.expected_espn_calls == len(plan.espn_requests)
    assert len(plan.espn_requests) >= 1


def test_planner_pregame_hot_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-hot", status="scheduled", scheduled_start=now + timedelta(minutes=45))
    plan = build_fetch_plan(db_session, "NBA", now=now)

    assert plan.mode == "pregame_hot"
    assert plan.next_ingest_seconds == 900
    assert len(plan.espn_requests) >= 1


def test_planner_pregame_cold_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-cold", status="scheduled", scheduled_start=now + timedelta(hours=12))
    plan = build_fetch_plan(db_session, "NBA", now=now)
    assert plan.mode == "pregame_cold"
    assert plan.next_ingest_seconds == 3600
    assert len(plan.espn_requests) >= 1


def test_planner_off_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(
        db_session,
        external_id="g-final",
        status="final",
        scheduled_start=now - timedelta(days=1),
        is_final=True,
    )
    plan = build_fetch_plan(db_session, "NBA", now=now)
    assert plan.mode == "off"
    assert plan.next_ingest_seconds == 43200
    assert len(plan.espn_requests) == 9


def test_planner_catalog_horizon_spans_yesterday_through_seven_days_ahead(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    plan = build_fetch_plan(db_session, "NBA", now=now)
    dates = [request.date for request in plan.espn_requests]
    assert "20260502" in dates
    assert "20260503" in dates
    assert "20260504" in dates
    assert "20260510" in dates
    assert len(dates) == 9


def test_planner_catalog_horizon_does_not_shrink_when_games_exist(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    _seed_game(db_session, external_id="g-existing", status="scheduled", scheduled_start=now + timedelta(days=4))
    plan = build_fetch_plan(db_session, "NBA", now=now)
    dates = [request.date for request in plan.espn_requests]
    assert "20260502" in dates
    assert "20260510" in dates
    assert len(dates) == 9


def test_planner_odds_refresh_disabled(db_session):
    plan = build_fetch_plan(db_session, "NBA")
    assert plan.expected_odds_calls in {0, 1}


def test_planner_odds_refresh_when_snapshot_missing(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-odds", status="scheduled", scheduled_start=now + timedelta(hours=1))
    db_session.add(
        GameOddsCurrent(
            game_id=db_session.scalar(select(Game.id).where(Game.external_game_id == "g-odds")),
            provider="the_odds_api",
            market="h2h",
            fetched_at=now - timedelta(hours=3),
        )
    )
    db_session.commit()

    monkeypatch.setattr("worker.planner.settings.odds_enabled", True)
    monkeypatch.setattr("worker.planner.settings.odds_provider", "the_odds_api")
    monkeypatch.setattr("worker.planner.settings.odds_api_market", "h2h")
    monkeypatch.setattr("worker.planner.settings.odds_pregame_window_hours", 24)

    plan = build_fetch_plan(db_session, "NBA", now=now)
    assert plan.odds_refresh is False
    assert plan.expected_odds_calls == 0


def test_build_catalog_requests_returns_fixed_horizon(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    requests = build_catalog_requests(db_session, "NBA", now=now)
    dates = [request.date for request in requests]
    assert "20260502" in dates
    assert "20260510" in dates
    assert len(dates) == 9


def test_build_live_requests_tracks_live_and_imminent_scheduled_games(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    _seed_game(db_session, external_id="g-live-sync", status="live", scheduled_start=now + timedelta(hours=1))
    _seed_game(db_session, external_id="g-imminent", status="scheduled", scheduled_start=now + timedelta(hours=2))
    _seed_game(db_session, external_id="g-far-future", status="scheduled", scheduled_start=now + timedelta(days=2))
    requests = build_live_requests(db_session, "NBA", now=now)
    dates = [request.date for request in requests]
    assert len(dates) >= 1
    assert (now + timedelta(hours=1)).strftime("%Y%m%d") in dates
    assert (now + timedelta(hours=2)).strftime("%Y%m%d") in dates
    assert (now + timedelta(days=2)).strftime("%Y%m%d") not in dates
