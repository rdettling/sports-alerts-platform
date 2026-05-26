"""refactor alert preferences to league defaults + game overrides

Revision ID: 0010_alert_defaults_overrides
Revises: 0009_user_game_unfollows
Create Date: 2026-05-25 22:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_alert_defaults_overrides"
down_revision = "0009_user_game_unfollows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_alert_defaults",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("close_game_margin_threshold", sa.Integer(), nullable=True),
        sa.Column("close_game_time_threshold_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "league", "alert_type", name="uq_user_alert_defaults_user_league_type"),
    )
    op.create_index(op.f("ix_user_alert_defaults_id"), "user_alert_defaults", ["id"], unique=False)

    op.create_table(
        "user_game_alert_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("is_enabled_override", sa.Boolean(), nullable=True),
        sa.Column("close_game_margin_threshold_override", sa.Integer(), nullable=True),
        sa.Column("close_game_time_threshold_seconds_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_id", "alert_type", name="uq_user_game_alert_overrides_user_game_type"),
    )
    op.create_index(op.f("ix_user_game_alert_overrides_id"), "user_game_alert_overrides", ["id"], unique=False)
    op.create_index("ix_user_game_alert_overrides_user_game", "user_game_alert_overrides", ["user_id", "game_id"], unique=False)

    op.drop_constraint("uq_user_alert_preferences_user_type", "user_alert_preferences", type_="unique")
    op.drop_table("user_alert_preferences")


def downgrade() -> None:
    op.create_table(
        "user_alert_preferences",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("alert_type", sa.VARCHAR(length=32), autoincrement=False, nullable=False),
        sa.Column("is_enabled", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column("close_game_margin_threshold", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("close_game_time_threshold_seconds", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("user_alert_preferences_user_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("user_alert_preferences_pkey")),
        sa.UniqueConstraint("user_id", "alert_type", name="uq_user_alert_preferences_user_type"),
    )
    op.drop_index("ix_user_game_alert_overrides_user_game", table_name="user_game_alert_overrides")
    op.drop_index(op.f("ix_user_game_alert_overrides_id"), table_name="user_game_alert_overrides")
    op.drop_table("user_game_alert_overrides")

    op.drop_index(op.f("ix_user_alert_defaults_id"), table_name="user_alert_defaults")
    op.drop_table("user_alert_defaults")
