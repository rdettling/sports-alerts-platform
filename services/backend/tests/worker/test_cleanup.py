from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Alert, AlertDelivery, Game, GameOddsCurrent, GameOddsOutcomeCurrent, Team, User, UserGameAlertOverride, UserGameFollow, UserGameUnfollow
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
    user = User(email="cleanup@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.add_all(
        [
            GameOddsCurrent(
                game_id=old_game.id,
                provider="the_odds_api",
                market="h2h",
                fetched_at=datetime.now(timezone.utc),
            ),
            Alert(
                user_id=user.id,
                game_id=old_game.id,
                alert_type="close_game",
                event_key="cleanup-old-game-alert",
                deliveries=[AlertDelivery(channel="email", status="sent")],
            ),
            UserGameAlertOverride(
                user_id=user.id,
                game_id=old_game.id,
                alert_type="close_game",
                is_enabled_override=True,
            ),
            UserGameFollow(user_id=user.id, game_id=old_game.id),
            UserGameUnfollow(user_id=user.id, game_id=old_game.id),
        ]
    )
    db_session.flush()
    old_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == old_game.id))
    assert old_odds is not None
    old_odds.outcomes.extend(
        [
            GameOddsOutcomeCurrent(outcome_key="away", outcome_label="Away", outcome_order=0, price_american=110, team_side="away"),
            GameOddsOutcomeCurrent(outcome_key="home", outcome_label="Home", outcome_order=1, price_american=-120, team_side="home"),
        ]
    )
    db_session.commit()

    removed = cleanup_games_outside_window(db_session)
    db_session.commit()

    assert removed == 1
    remaining_ids = {g.external_game_id for g in db_session.scalars(select(Game)).all()}
    assert "old-outside-window" not in remaining_ids
    assert "current-in-window" in remaining_ids
