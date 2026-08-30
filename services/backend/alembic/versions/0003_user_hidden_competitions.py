"""Store each user's hidden competitions.

Revision ID: 0003_user_hidden_competitions
Revises: 0002_game_broadcast_names
Create Date: 2026-08-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_user_hidden_competitions"
down_revision: Union[str, None] = "0002_game_broadcast_names"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "hidden_competitions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "hidden_competitions")
