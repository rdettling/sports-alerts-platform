"""Reset sport preferences to independent league preferences.

Only user_alert_preferences is replaced. Game overrides remain intact.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_league_preferences"
down_revision = "0001_sqlite"
branch_labels = None
depends_on = None


def _create_preferences(scope: str, length: int) -> None:
    op.create_table(
        "user_alert_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(scope, sa.String(length), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("is_enabled_override", sa.Boolean(), nullable=True),
        sa.Column("close_game_margin_threshold_override", sa.Integer(), nullable=True),
        sa.Column(
            "close_game_time_threshold_seconds_override", sa.Integer(), nullable=True
        ),
        sa.Column("inning_start_threshold_override", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            scope,
            "alert_type",
            name=f"uq_user_alert_preferences_user_{scope}_type",
        ),
    )
    op.create_index("ix_user_alert_preferences_id", "user_alert_preferences", ["id"])


def upgrade() -> None:
    op.drop_table("user_alert_preferences")
    _create_preferences("competition", 32)


def downgrade() -> None:
    op.drop_table("user_alert_preferences")
    _create_preferences("sport", 16)
