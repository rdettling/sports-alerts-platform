from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, Team
from worker.cleanup import cleanup_games_outside_window


def test_cleanup_removes_games_outside_window(db_session):
    teams = db_session.scalars(select(Team).order_by(Team.id.asc()).limit(2)).all()
    old_game = Game(
        external_game_id="old-outside-window",
        league="NBA",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc) - timedelta(days=8),
        status="scheduled",
        is_final=False,
    )
    current_game = Game(
        external_game_id="current-in-window",
        league="NBA",
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        status="scheduled",
        is_final=False,
    )
    db_session.add_all([old_game, current_game])
    db_session.commit()

    removed = cleanup_games_outside_window(db_session)
    db_session.commit()

    assert removed == 1
    remaining_ids = {g.external_game_id for g in db_session.scalars(select(Game)).all()}
    assert "old-outside-window" not in remaining_ids
    assert "current-in-window" in remaining_ids
