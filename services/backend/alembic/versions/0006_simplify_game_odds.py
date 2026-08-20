"""simplify current game odds

Revision ID: 0006_simplify_game_odds
Revises: 0005_remove_worker_jobs
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006_simplify_game_odds"
down_revision: Union[str, None] = "0005_remove_worker_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM game_odds_current")
    op.drop_constraint(
        "uq_game_odds_current_game_provider_market",
        "game_odds_current",
        type_="unique",
    )
    op.drop_column("game_odds_current", "provider")
    op.drop_column("game_odds_current", "market")
    op.drop_index("ix_game_odds_current_game_id", table_name="game_odds_current")
    op.create_unique_constraint(
        "uq_game_odds_current_game_id",
        "game_odds_current",
        ["game_id"],
    )


def downgrade() -> None:
    pass
