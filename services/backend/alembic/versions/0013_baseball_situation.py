"""Store baseball outs and occupied bases.

Revision ID: 0013_baseball_situation
Revises: 0012_game_down_distance
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_baseball_situation"
down_revision = "0012_game_down_distance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("outs", sa.Integer(), nullable=True))
    for name in ("on_first", "on_second", "on_third"):
        op.add_column("games", sa.Column(name, sa.Boolean(), nullable=True))


def downgrade() -> None:
    for name in ("on_third", "on_second", "on_first", "outs"):
        op.drop_column("games", name)
