from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, Team
from app.worker.planner import build_catalog_requests, build_live_requests


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


def test_build_catalog_requests_returns_fixed_horizon(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    requests = build_catalog_requests(db_session, "NBA", now=now)
    assert "20260502" in requests
    assert "20260510" in requests
    assert len(requests) == 9


def test_build_live_requests_tracks_live_and_imminent_scheduled_games(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    _seed_game(db_session, external_id="g-live-sync", status="live", scheduled_start=now + timedelta(hours=1))
    _seed_game(db_session, external_id="g-imminent", status="scheduled", scheduled_start=now + timedelta(hours=2))
    _seed_game(db_session, external_id="g-far-future", status="scheduled", scheduled_start=now + timedelta(days=2))
    requests = build_live_requests(db_session, "NBA", now=now)
    assert len(requests) >= 1
    assert (now + timedelta(hours=1)).strftime("%Y%m%d") in requests
    assert (now + timedelta(hours=2)).strftime("%Y%m%d") in requests
    assert (now + timedelta(days=2)).strftime("%Y%m%d") not in requests


def test_build_catalog_requests_stays_fixed_when_games_exist(db_session):
    now = datetime(2026, 5, 3, 1, 0, tzinfo=timezone.utc)
    _seed_game(db_session, external_id="g-existing", status="scheduled", scheduled_start=now + timedelta(days=4))
    requests = build_catalog_requests(db_session, "NBA", now=now)
    assert "20260502" in requests
    assert "20260510" in requests
    assert len(requests) == 9
