from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, Team
from worker.planner import build_fetch_plan


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
    plan = build_fetch_plan(db_session, now=now)

    assert plan.mode == "live"
    assert plan.next_ingest_seconds == 120
    assert plan.expected_espn_calls == len(plan.espn_requests)
    assert len(plan.espn_requests) >= 1


def test_planner_pregame_hot_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-hot", status="scheduled", scheduled_start=now + timedelta(minutes=45))
    plan = build_fetch_plan(db_session, now=now)

    assert plan.mode == "pregame_hot"
    assert plan.next_ingest_seconds == 900
    assert len(plan.espn_requests) >= 1


def test_planner_pregame_cold_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-cold", status="scheduled", scheduled_start=now + timedelta(hours=12))
    plan = build_fetch_plan(db_session, now=now)
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
    plan = build_fetch_plan(db_session, now=now)
    assert plan.mode == "off"
    assert plan.next_ingest_seconds == 43200
    assert len(plan.espn_requests) == 3


def test_planner_always_includes_yesterday_today_tomorrow(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    plan = build_fetch_plan(db_session, now=now)
    dates = [request.date for request in plan.espn_requests]
    assert "20260502" in dates
    assert "20260503" in dates
    assert "20260504" in dates


def test_planner_cold_start_extends_date_window(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    plan = build_fetch_plan(db_session, now=now)
    dates = [request.date for request in plan.espn_requests]
    assert "20260501" in dates
    assert "20260510" in dates
    assert len(dates) == 10


def test_planner_does_not_use_cold_start_window_when_games_exist(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    _seed_game(db_session, external_id="g-existing", status="scheduled", scheduled_start=now + timedelta(days=4))
    plan = build_fetch_plan(db_session, now=now)
    dates = [request.date for request in plan.espn_requests]
    assert "20260501" not in dates
    assert "20260510" not in dates


def test_planner_odds_refresh_disabled(db_session):
    plan = build_fetch_plan(db_session)
    assert plan.expected_odds_calls in {0, 1}


def test_planner_odds_refresh_stale_cache(db_session, monkeypatch):
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
    monkeypatch.setattr("worker.planner.settings.odds_refresh_seconds", 120)
    monkeypatch.setattr("worker.planner.settings.odds_provider", "the_odds_api")
    monkeypatch.setattr("worker.planner.settings.odds_api_market", "h2h")

    plan = build_fetch_plan(db_session, now=now)
    assert plan.odds_refresh is True
    assert plan.expected_odds_calls == 1
