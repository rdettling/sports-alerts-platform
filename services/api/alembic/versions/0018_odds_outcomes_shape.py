"""replace moneyline odds with outcome rows

Revision ID: 0018_odds_outcomes_shape
Revises: 0017_game_context_label
Create Date: 2026-06-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0018_odds_outcomes_shape"
down_revision: Union[str, None] = "0017_game_context_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "game_odds_outcomes_current" in inspector.get_table_names():
        op.drop_index("ix_game_odds_outcomes_current_odds_id", table_name="game_odds_outcomes_current")
        op.drop_constraint("uq_game_odds_outcomes_current_odds_outcome_order", "game_odds_outcomes_current", type_="unique")
        op.drop_constraint("uq_game_odds_outcomes_current_odds_outcome_key", "game_odds_outcomes_current", type_="unique")
        op.drop_table("game_odds_outcomes_current")

    if "game_odds_current" in inspector.get_table_names():
        op.drop_index("ix_game_odds_current_game_id", table_name="game_odds_current")
        op.drop_constraint("uq_game_odds_current_game_provider_market", "game_odds_current", type_="unique")
        op.drop_table("game_odds_current")

    op.create_table(
        "game_odds_current",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
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

    op.create_table(
        "game_odds_outcomes_current",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("odds_id", sa.Integer(), sa.ForeignKey("game_odds_current.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_key", sa.String(length=32), nullable=False),
        sa.Column("outcome_label", sa.String(length=80), nullable=False),
        sa.Column("outcome_order", sa.Integer(), nullable=False),
        sa.Column("price_american", sa.Integer(), nullable=True),
        sa.Column("team_side", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_game_odds_outcomes_current_odds_outcome_key",
        "game_odds_outcomes_current",
        ["odds_id", "outcome_key"],
    )
    op.create_unique_constraint(
        "uq_game_odds_outcomes_current_odds_outcome_order",
        "game_odds_outcomes_current",
        ["odds_id", "outcome_order"],
    )
    op.create_index("ix_game_odds_outcomes_current_odds_id", "game_odds_outcomes_current", ["odds_id"])


def downgrade() -> None:
    op.drop_index("ix_game_odds_outcomes_current_odds_id", table_name="game_odds_outcomes_current")
    op.drop_constraint("uq_game_odds_outcomes_current_odds_outcome_order", "game_odds_outcomes_current", type_="unique")
    op.drop_constraint("uq_game_odds_outcomes_current_odds_outcome_key", "game_odds_outcomes_current", type_="unique")
    op.drop_table("game_odds_outcomes_current")

    op.drop_index("ix_game_odds_current_game_id", table_name="game_odds_current")
    op.drop_constraint("uq_game_odds_current_game_provider_market", "game_odds_current", type_="unique")
    op.drop_table("game_odds_current")

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
