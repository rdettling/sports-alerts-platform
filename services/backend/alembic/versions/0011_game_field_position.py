"""Store football field-position display text.

Revision ID: 0011_game_field_position
Revises: 0010_game_possession
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_game_field_position"
down_revision = "0010_game_possession"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("field_position", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "field_position")
