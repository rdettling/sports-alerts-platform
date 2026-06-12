"""league runtime settings

Revision ID: 0016_league_runtime_settings
Revises: 0015_remove_updates_feature
Create Date: 2026-06-11 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_league_runtime_settings"
down_revision: Union[str, None] = "0015_remove_updates_feature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "league_settings",
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("league"),
    )
    op.create_index(op.f("ix_league_settings_is_enabled"), "league_settings", ["is_enabled"], unique=False)
    op.bulk_insert(
        sa.table(
            "league_settings",
            sa.column("league", sa.String()),
            sa.column("is_enabled", sa.Boolean()),
        ),
        [
            {"league": "NBA", "is_enabled": True},
            {"league": "MLB", "is_enabled": True},
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_league_settings_is_enabled"), table_name="league_settings")
    op.drop_table("league_settings")
