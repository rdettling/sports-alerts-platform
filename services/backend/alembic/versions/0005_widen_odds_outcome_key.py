"""Allow odds keys for long team names.

Revision ID: 0005_widen_odds_outcome_key
Revises: 0004_competition_team_strength
Create Date: 2026-09-04 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_widen_odds_outcome_key"
down_revision: Union[str, None] = "0004_competition_team_strength"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("game_odds_outcomes_current") as batch_op:
        batch_op.alter_column(
            "outcome_key",
            existing_type=sa.String(32),
            type_=sa.String(128),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("game_odds_outcomes_current") as batch_op:
        batch_op.alter_column(
            "outcome_key",
            existing_type=sa.String(128),
            type_=sa.String(32),
            existing_nullable=False,
        )
