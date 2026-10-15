"""Store football down-and-distance display text.

Revision ID: 0012_game_down_distance
Revises: 0011_game_field_position
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_game_down_distance"
down_revision = "0011_game_field_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("down_distance", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "down_distance")
