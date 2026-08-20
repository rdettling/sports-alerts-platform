"""remove api call rollups

Revision ID: 0007_remove_api_call_rollups
Revises: 0006_simplify_game_odds
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0007_remove_api_call_rollups"
down_revision: Union[str, None] = "0006_simplify_game_odds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("api_call_rollups_hourly")


def downgrade() -> None:
    pass
