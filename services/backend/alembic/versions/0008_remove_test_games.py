"""remove synthetic test games

Revision ID: 0008_remove_test_games
Revises: 0007_remove_api_call_rollups
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0008_remove_test_games"
down_revision: Union[str, None] = "0007_remove_api_call_rollups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    test_game_ids = "SELECT id FROM games WHERE is_test = true"
    test_alert_ids = f"SELECT id FROM alerts WHERE game_id IN ({test_game_ids})"
    op.execute(f"DELETE FROM alert_deliveries WHERE alert_id IN ({test_alert_ids})")
    op.execute(f"DELETE FROM alerts WHERE game_id IN ({test_game_ids})")
    op.execute(f"DELETE FROM user_game_alert_overrides WHERE game_id IN ({test_game_ids})")
    op.execute(f"DELETE FROM user_game_unfollows WHERE game_id IN ({test_game_ids})")
    op.execute(f"DELETE FROM user_game_follows WHERE game_id IN ({test_game_ids})")
    op.execute(f"DELETE FROM game_odds_current WHERE game_id IN ({test_game_ids})")
    op.execute("DELETE FROM games WHERE is_test = true")
    op.drop_column("games", "is_test")


def downgrade() -> None:
    pass
