"""add game context label

Revision ID: 0017_game_context_label
Revises: 0016_league_runtime_settings
Create Date: 2026-06-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_game_context_label"
down_revision: Union[str, None] = "0016_league_runtime_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("games", sa.Column("context_label", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "context_label")
