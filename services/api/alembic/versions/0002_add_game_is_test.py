"""add is_test flag to games

Revision ID: 0002_add_game_is_test
Revises: 0001_baseline
Create Date: 2026-06-20 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_game_is_test"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("games", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("games", "is_test", server_default=None)


def downgrade() -> None:
    op.drop_column("games", "is_test")
