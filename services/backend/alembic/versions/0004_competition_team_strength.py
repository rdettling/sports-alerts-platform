"""Store current structured strength on competition teams.

Revision ID: 0004_competition_team_strength
Revises: 0003_user_hidden_competitions
Create Date: 2026-08-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_competition_team_strength"
down_revision: Union[str, None] = "0003_user_hidden_competitions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("competition_teams", sa.Column("wins", sa.Integer(), nullable=True))
    op.add_column("competition_teams", sa.Column("losses", sa.Integer(), nullable=True))
    op.add_column("competition_teams", sa.Column("ties", sa.Integer(), nullable=True))
    op.add_column("competition_teams", sa.Column("rank", sa.Integer(), nullable=True))
    op.add_column(
        "competition_teams",
        sa.Column("strength_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_column("games", "away_team_record")
    op.drop_column("games", "home_team_record")


def downgrade() -> None:
    op.add_column("games", sa.Column("home_team_record", sa.String(32), nullable=True))
    op.add_column("games", sa.Column("away_team_record", sa.String(32), nullable=True))
    op.drop_column("competition_teams", "strength_updated_at")
    op.drop_column("competition_teams", "rank")
    op.drop_column("competition_teams", "ties")
    op.drop_column("competition_teams", "losses")
    op.drop_column("competition_teams", "wins")
