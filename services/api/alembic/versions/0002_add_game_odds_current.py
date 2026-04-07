"""add game odds current

Revision ID: 0002_add_game_odds_current
Revises: 0001_initial_schema
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_game_odds_current"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_games_is_final_scheduled_start", "games", ["is_final", "scheduled_start_time"])
    op.create_index("ix_games_status_scheduled_start", "games", ["status", "scheduled_start_time"])

    op.create_table(
        "game_odds_current",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("home_moneyline", sa.Integer(), nullable=True),
        sa.Column("away_moneyline", sa.Integer(), nullable=True),
        sa.Column("bookmaker", sa.String(length=80), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_game_odds_current_game_provider_market",
        "game_odds_current",
        ["game_id", "provider", "market"],
    )
    op.create_index("ix_game_odds_current_game_id", "game_odds_current", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_game_odds_current_game_id", table_name="game_odds_current")
    op.drop_constraint("uq_game_odds_current_game_provider_market", "game_odds_current", type_="unique")
    op.drop_table("game_odds_current")
    op.drop_index("ix_games_status_scheduled_start", table_name="games")
    op.drop_index("ix_games_is_final_scheduled_start", table_name="games")
