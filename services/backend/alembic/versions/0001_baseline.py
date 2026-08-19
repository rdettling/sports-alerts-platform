"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

metadata = sa.MetaData()
timestamp = sa.func.now()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
    sa.Column("role", sa.Enum("user", "admin", name="user_role"), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
)

email_login_tokens = sa.Table(
    "email_login_tokens",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("email", sa.String(320), nullable=False, index=True),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column("requested_ip", sa.String(64), nullable=True),
    sa.Column("requested_user_agent", sa.String(255), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp, index=True),
)

teams = sa.Table(
    "teams",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("external_team_id", sa.String(64), nullable=False),
    sa.Column("league", sa.String(16), nullable=False),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("abbreviation", sa.String(10), nullable=False),
    sa.UniqueConstraint("external_team_id", "league", name="uq_teams_external_league"),
)

league_settings = sa.Table(
    "league_settings",
    metadata,
    sa.Column("league", sa.String(16), primary_key=True),
    sa.Column("is_enabled", sa.Boolean(), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
)

games = sa.Table(
    "games",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("external_game_id", sa.String(64), nullable=False),
    sa.Column("league", sa.String(16), nullable=False),
    sa.Column("home_team_id", sa.ForeignKey("teams.id"), nullable=False),
    sa.Column("away_team_id", sa.ForeignKey("teams.id"), nullable=False),
    sa.Column("scheduled_start_time", sa.DateTime(timezone=True), nullable=False),
    sa.Column("context_label", sa.String(255), nullable=True),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("home_score", sa.Integer(), nullable=True),
    sa.Column("away_score", sa.Integer(), nullable=True),
    sa.Column("period", sa.Integer(), nullable=True),
    sa.Column("clock", sa.String(64), nullable=True),
    sa.Column("is_final", sa.Boolean(), nullable=False),
    sa.Column("is_test", sa.Boolean(), nullable=False),
    sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("external_game_id", "league", name="uq_games_external_league"),
    sa.Index("ix_games_league_is_final_status_sched", "league", "is_final", "status", "scheduled_start_time"),
)

game_odds_current = sa.Table(
    "game_odds_current",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("game_id", sa.ForeignKey("games.id"), nullable=False, index=True),
    sa.Column("provider", sa.String(32), nullable=False),
    sa.Column("market", sa.String(16), nullable=False),
    sa.Column("bookmaker", sa.String(80), nullable=True),
    sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("game_id", "provider", "market", name="uq_game_odds_current_game_provider_market"),
)

game_odds_outcomes_current = sa.Table(
    "game_odds_outcomes_current",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("odds_id", sa.ForeignKey("game_odds_current.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("outcome_key", sa.String(32), nullable=False),
    sa.Column("outcome_label", sa.String(80), nullable=False),
    sa.Column("outcome_order", sa.Integer(), nullable=False),
    sa.Column("price_american", sa.Integer(), nullable=True),
    sa.Column("team_side", sa.String(16), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("odds_id", "outcome_key", name="uq_game_odds_outcomes_current_odds_outcome_key"),
    sa.UniqueConstraint("odds_id", "outcome_order", name="uq_game_odds_outcomes_current_odds_outcome_order"),
)

user_team_follows = sa.Table(
    "user_team_follows",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False),
    sa.Column("team_id", sa.ForeignKey("teams.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("user_id", "team_id", name="uq_user_team_follows_user_team"),
)

user_game_follows = sa.Table(
    "user_game_follows",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False),
    sa.Column("game_id", sa.ForeignKey("games.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("user_id", "game_id", name="uq_user_game_follows_user_game"),
)

user_game_unfollows = sa.Table(
    "user_game_unfollows",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False),
    sa.Column("game_id", sa.ForeignKey("games.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("user_id", "game_id", name="uq_user_game_unfollows_user_game"),
)

user_alert_defaults = sa.Table(
    "user_alert_defaults",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False),
    sa.Column("league", sa.String(16), nullable=False),
    sa.Column("alert_type", sa.String(32), nullable=False),
    sa.Column("is_enabled", sa.Boolean(), nullable=False),
    sa.Column("close_game_margin_threshold", sa.Integer(), nullable=True),
    sa.Column("close_game_time_threshold_seconds", sa.Integer(), nullable=True),
    sa.Column("inning_start_threshold", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("user_id", "league", "alert_type", name="uq_user_alert_defaults_user_league_type"),
)

user_game_alert_overrides = sa.Table(
    "user_game_alert_overrides",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False),
    sa.Column("game_id", sa.ForeignKey("games.id"), nullable=False),
    sa.Column("alert_type", sa.String(32), nullable=False),
    sa.Column("is_enabled_override", sa.Boolean(), nullable=True),
    sa.Column("close_game_margin_threshold_override", sa.Integer(), nullable=True),
    sa.Column("close_game_time_threshold_seconds_override", sa.Integer(), nullable=True),
    sa.Column("inning_start_threshold_override", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp),
    sa.UniqueConstraint("user_id", "game_id", "alert_type", name="uq_user_game_alert_overrides_user_game_type"),
    sa.Index("ix_user_game_alert_overrides_user_game", "user_id", "game_id"),
)

alerts = sa.Table(
    "alerts",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("user_id", sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("game_id", sa.ForeignKey("games.id"), nullable=False, index=True),
    sa.Column("alert_type", sa.String(32), nullable=False),
    sa.Column("event_key", sa.String(255), nullable=False, unique=True),
    sa.Column("event_data", sa.JSON(), nullable=True),
    sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp, index=True),
)

alert_deliveries = sa.Table(
    "alert_deliveries",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("alert_id", sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True),
    sa.Column("channel", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("provider_message_id", sa.String(128), nullable=True),
    sa.Column("provider_data", sa.JSON(), nullable=True),
    sa.UniqueConstraint("alert_id", "channel", name="uq_alert_deliveries_alert_channel"),
    sa.Index("ix_alert_deliveries_channel_attempted_at", "channel", "attempted_at"),
)

api_call_rollups_hourly = sa.Table(
    "api_call_rollups_hourly",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("service", sa.String(16), nullable=False, index=True),
    sa.Column("provider", sa.String(32), nullable=False, index=True),
    sa.Column("endpoint_key", sa.String(64), nullable=False, index=True),
    sa.Column("attempt_status", sa.String(32), nullable=False, index=True),
    sa.Column("call_count", sa.Integer(), nullable=False),
    sa.UniqueConstraint(
        "bucket_start",
        "service",
        "provider",
        "endpoint_key",
        "attempt_status",
        name="uq_api_call_rollups_hourly_bucket_dims",
    ),
)

worker_jobs = sa.Table(
    "worker_jobs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, index=True),
    sa.Column("job_type", sa.String(32), nullable=False, index=True),
    sa.Column("league", sa.String(16), nullable=True, index=True),
    sa.Column("status", sa.String(16), nullable=False, index=True),
    sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("max_attempts", sa.Integer(), nullable=False),
    sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("backoff_until", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.UniqueConstraint("job_type", "league", name="uq_worker_jobs_job_type_league"),
    sa.Index("ix_worker_jobs_status_next_run", "status", "next_run_at"),
)


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
