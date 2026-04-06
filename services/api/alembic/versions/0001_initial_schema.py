"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_team_id", sa.String(length=64), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("abbreviation", sa.String(length=10), nullable=False),
    )
    op.create_unique_constraint("uq_teams_external_league", "teams", ["external_team_id", "league"])

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_game_id", sa.String(length=64), nullable=False),
        sa.Column("league", sa.String(length=16), nullable=False),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("scheduled_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("clock", sa.String(length=20), nullable=True),
        sa.Column("is_final", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_games_external_league", "games", ["external_game_id", "league"])

    op.create_table(
        "user_team_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_user_team_follows_user_team", "user_team_follows", ["user_id", "team_id"])

    op.create_table(
        "user_game_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_user_game_follows_user_game", "user_game_follows", ["user_id", "game_id"])

    op.create_table(
        "user_alert_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("close_game_margin_threshold", sa.Integer(), nullable=True),
        sa.Column("close_game_time_threshold_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_user_alert_preferences_user_type", "user_alert_preferences", ["user_id", "alert_type"])

    op.create_table(
        "sent_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("delivery_channel", sa.String(length=32), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_unique_constraint("uq_sent_alerts_dedupe_key", "sent_alerts", ["dedupe_key"])
    op.create_index("ix_sent_alerts_user_id", "sent_alerts", ["user_id"])

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("games_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("games_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingest_runs")
    op.drop_index("ix_sent_alerts_user_id", table_name="sent_alerts")
    op.drop_constraint("uq_sent_alerts_dedupe_key", "sent_alerts", type_="unique")
    op.drop_table("sent_alerts")
    op.drop_constraint("uq_user_alert_preferences_user_type", "user_alert_preferences", type_="unique")
    op.drop_table("user_alert_preferences")
    op.drop_constraint("uq_user_game_follows_user_game", "user_game_follows", type_="unique")
    op.drop_table("user_game_follows")
    op.drop_constraint("uq_user_team_follows_user_team", "user_team_follows", type_="unique")
    op.drop_table("user_team_follows")
    op.drop_constraint("uq_games_external_league", "games", type_="unique")
    op.drop_table("games")
    op.drop_constraint("uq_teams_external_league", "teams", type_="unique")
    op.drop_table("teams")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_table("users")
