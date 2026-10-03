"""Store hockey overtime losses on competition teams.

Revision ID: 0007_hockey_overtime_losses
Revises: 0006_decouple_odds_sync
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_hockey_overtime_losses"
down_revision: Union[str, None] = "0006_decouple_odds_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competition_teams",
        sa.Column("overtime_losses", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competition_teams", "overtime_losses")
