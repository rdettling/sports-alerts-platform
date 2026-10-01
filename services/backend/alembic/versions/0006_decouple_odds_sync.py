"""Decouple scheduled odds sync from catalog ingest.

Revision ID: 0006_decouple_odds_sync
Revises: 0005_widen_odds_outcome_key
Create Date: 2026-09-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006_decouple_odds_sync"
down_revision: Union[str, None] = "0005_widen_odds_outcome_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("games") as batch_op:
        batch_op.add_column(sa.Column("is_neutral_site", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("is_odds_eligible", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "odds_api_daily_usage",
        sa.Column("usage_date", sa.Date(), primary_key=True),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_credits_used", sa.Integer(), nullable=True),
        sa.Column("provider_credits_remaining", sa.Integer(), nullable=True),
        sa.Column("provider_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("odds_api_daily_usage")
    with op.batch_alter_table("games") as batch_op:
        batch_op.drop_column("is_odds_eligible")
        batch_op.drop_column("is_neutral_site")
