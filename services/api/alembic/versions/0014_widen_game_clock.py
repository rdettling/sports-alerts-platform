"""widen game clock field

Revision ID: 0014_widen_game_clock
Revises: 0013_updates_feed
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_widen_game_clock"
down_revision: Union[str, None] = "0013_updates_feed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "games",
        "clock",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "games",
        "clock",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
