"""add inning start alert thresholds for mlb rules

Revision ID: 0011_mlb_inning_start
Revises: 0010_alert_defaults_overrides
Create Date: 2026-05-25 23:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_mlb_inning_start"
down_revision = "0010_alert_defaults_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_alert_defaults", sa.Column("inning_start_threshold", sa.Integer(), nullable=True))
    op.add_column("user_game_alert_overrides", sa.Column("inning_start_threshold_override", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_game_alert_overrides", "inning_start_threshold_override")
    op.drop_column("user_alert_defaults", "inning_start_threshold")
