"""set nba close-game default to 5 minutes

Revision ID: 0012_nba_close_game_5min
Revises: 0011_mlb_inning_start
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0012_nba_close_game_5min"
down_revision: Union[str, None] = "0011_mlb_inning_start"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_alert_defaults
        SET close_game_time_threshold_seconds = 300
        WHERE league = 'NBA'
          AND alert_type = 'close_game_late'
          AND (close_game_time_threshold_seconds = 120 OR close_game_time_threshold_seconds IS NULL)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE user_alert_defaults
        SET close_game_time_threshold_seconds = 120
        WHERE league = 'NBA'
          AND alert_type = 'close_game_late'
          AND close_game_time_threshold_seconds = 300
        """
    )
