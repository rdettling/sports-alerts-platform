"""Store the possessing side for live football games.

Revision ID: 0010_game_possession
Revises: 0009_prune_retired_setting
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_game_possession"
down_revision = "0009_prune_retired_setting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("possession_side", sa.String(4), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "possession_side")
