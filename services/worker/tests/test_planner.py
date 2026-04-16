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
    assert plan.next_ingest_seconds == 60
    assert plan.expected_espn_calls == len(plan.espn_requests)
    assert len(plan.espn_requests) >= 1


def test_planner_active_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    _seed_game(db_session, external_id="g-active", status="scheduled", scheduled_start=now + timedelta(hours=3))
    plan = build_fetch_plan(db_session, now=now)

    assert plan.mode == "active"
    assert plan.next_ingest_seconds == 300
    assert len(plan.espn_requests) >= 1


def test_planner_idle_mode_and_interval(db_session):
    now = datetime.now(timezone.utc)
    plan = build_fetch_plan(db_session, now=now)
    assert plan.mode == "idle"
    assert plan.next_ingest_seconds == 900
    assert len(plan.espn_requests) == 1


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
