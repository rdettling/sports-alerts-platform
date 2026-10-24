"""Fresh SQLite baseline. Existing installations start with a new database file."""

from alembic import op
import sqlalchemy as sa

revision = "0001_sqlite"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competition_settings",
        sa.Column("competition", sa.String(length=32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("competition"),
    )
    op.create_index(
        op.f("ix_competition_settings_is_enabled"),
        "competition_settings",
        ["is_enabled"],
        unique=False,
    )
    op.create_table(
        "email_login_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "failed_code_attempts", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("requested_user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_login_tokens_consumed_at"),
        "email_login_tokens",
        ["consumed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_login_tokens_created_at"),
        "email_login_tokens",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_login_tokens_email"),
        "email_login_tokens",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_login_tokens_expires_at"),
        "email_login_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_login_tokens_id"), "email_login_tokens", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_email_login_tokens_token_hash"),
        "email_login_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_table(
        "odds_api_daily_usage",
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("credits_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_credits_used", sa.Integer(), nullable=True),
        sa.Column("provider_credits_remaining", sa.Integer(), nullable=True),
        sa.Column("provider_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("usage_date"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport", sa.String(length=16), nullable=False),
        sa.Column("provider_scope", sa.String(length=32), nullable=False),
        sa.Column("external_team_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("abbreviation", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_scope",
            "external_team_id",
            name="uq_teams_provider_scope_external",
        ),
    )
    op.create_index(op.f("ix_teams_id"), "teams", ["id"], unique=False)
    op.create_index(op.f("ix_teams_sport"), "teams", ["sport"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.Enum("user", "admin", name="user_role"), nullable=False),
        sa.Column(
            "email_alerts_enabled", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "hidden_competitions", sa.JSON(), server_default="[]", nullable=False
        ),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_table(
        "competition_teams",
        sa.Column("competition", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("ties", sa.Integer(), nullable=True),
        sa.Column("overtime_losses", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("strength_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["competition"],
            ["competition_settings.competition"],
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
        ),
        sa.PrimaryKeyConstraint("competition", "team_id"),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_game_id", sa.String(length=64), nullable=False),
        sa.Column("competition", sa.String(length=32), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context_label", sa.String(length=255), nullable=True),
        sa.Column("broadcast_names", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("clock", sa.String(length=64), nullable=True),
        sa.Column("possession_side", sa.String(length=4), nullable=True),
        sa.Column("field_position", sa.String(length=64), nullable=True),
        sa.Column("down_distance", sa.String(length=64), nullable=True),
        sa.Column("outs", sa.Integer(), nullable=True),
        sa.Column("on_first", sa.Boolean(), nullable=True),
        sa.Column("on_second", sa.Boolean(), nullable=True),
        sa.Column("on_third", sa.Boolean(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column(
            "is_neutral_site", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_odds_eligible", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["away_team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["competition"],
            ["competition_settings.competition"],
        ),
        sa.ForeignKeyConstraint(
            ["home_team_id"],
            ["teams.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "external_game_id", "competition", name="uq_games_external_competition"
        ),
    )
    op.create_index(
        "ix_games_competition_is_final_status_sched",
        "games",
        ["competition", "is_final", "status", "scheduled_start_time"],
        unique=False,
    )
    op.create_index(op.f("ix_games_id"), "games", ["id"], unique=False)
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(
        op.f("ix_push_subscriptions_id"), "push_subscriptions", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_push_subscriptions_user_id"),
        "push_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "user_alert_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sport", sa.String(length=16), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "sport",
            "alert_type",
            name="uq_user_alert_preferences_user_sport_type",
        ),
    )
    op.create_index(
        op.f("ix_user_alert_preferences_id"),
        "user_alert_preferences",
        ["id"],
        unique=False,
    )
    op.create_table(
        "user_team_follows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "team_id", name="uq_user_team_follows_user_team"
        ),
    )
    op.create_index(
        op.f("ix_user_team_follows_id"), "user_team_follows", ["id"], unique=False
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index(op.f("ix_alerts_game_id"), "alerts", ["game_id"], unique=False)
    op.create_index(op.f("ix_alerts_id"), "alerts", ["id"], unique=False)
    op.create_index(
        op.f("ix_alerts_triggered_at"), "alerts", ["triggered_at"], unique=False
    )
    op.create_index(op.f("ix_alerts_user_id"), "alerts", ["user_id"], unique=False)
    op.create_table(
        "game_odds_current",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker", sa.String(length=80), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", name="uq_game_odds_current_game_id"),
    )
    op.create_index(
        op.f("ix_game_odds_current_id"), "game_odds_current", ["id"], unique=False
    )
    op.create_table(
        "user_game_alert_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "game_id",
            "alert_type",
            name="uq_user_game_alert_overrides_user_game_type",
        ),
    )
    op.create_index(
        op.f("ix_user_game_alert_overrides_id"),
        "user_game_alert_overrides",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_user_game_alert_overrides_user_game",
        "user_game_alert_overrides",
        ["user_id", "game_id"],
        unique=False,
    )
    op.create_table(
        "user_game_follows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "game_id", name="uq_user_game_follows_user_game"
        ),
    )
    op.create_index(
        op.f("ix_user_game_follows_id"), "user_game_follows", ["id"], unique=False
    )
    op.create_table(
        "user_game_unfollows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "game_id", name="uq_user_game_unfollows_user_game"
        ),
    )
    op.create_index(
        op.f("ix_user_game_unfollows_id"), "user_game_unfollows", ["id"], unique=False
    )
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("provider_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "alert_id", "channel", name="uq_alert_deliveries_alert_channel"
        ),
    )
    op.create_index(
        op.f("ix_alert_deliveries_alert_id"),
        "alert_deliveries",
        ["alert_id"],
        unique=False,
    )
    op.create_index(
        "ix_alert_deliveries_channel_attempted_at",
        "alert_deliveries",
        ["channel", "attempted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_alert_deliveries_id"), "alert_deliveries", ["id"], unique=False
    )
    op.create_table(
        "game_odds_outcomes_current",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("odds_id", sa.Integer(), nullable=False),
        sa.Column("outcome_key", sa.String(length=128), nullable=False),
        sa.Column("outcome_label", sa.String(length=80), nullable=False),
        sa.Column("outcome_order", sa.Integer(), nullable=False),
        sa.Column("price_american", sa.Integer(), nullable=True),
        sa.Column("team_side", sa.String(length=16), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["odds_id"], ["game_odds_current.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "odds_id",
            "outcome_key",
            name="uq_game_odds_outcomes_current_odds_outcome_key",
        ),
        sa.UniqueConstraint(
            "odds_id",
            "outcome_order",
            name="uq_game_odds_outcomes_current_odds_outcome_order",
        ),
    )
    op.create_index(
        op.f("ix_game_odds_outcomes_current_id"),
        "game_odds_outcomes_current",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_game_odds_outcomes_current_odds_id"),
        "game_odds_outcomes_current",
        ["odds_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_game_odds_outcomes_current_odds_id"),
        table_name="game_odds_outcomes_current",
    )
    op.drop_index(
        op.f("ix_game_odds_outcomes_current_id"),
        table_name="game_odds_outcomes_current",
    )
    op.drop_table("game_odds_outcomes_current")
    op.drop_index(op.f("ix_alert_deliveries_id"), table_name="alert_deliveries")
    op.drop_index(
        "ix_alert_deliveries_channel_attempted_at", table_name="alert_deliveries"
    )
    op.drop_index(op.f("ix_alert_deliveries_alert_id"), table_name="alert_deliveries")
    op.drop_table("alert_deliveries")
    op.drop_index(op.f("ix_user_game_unfollows_id"), table_name="user_game_unfollows")
    op.drop_table("user_game_unfollows")
    op.drop_index(op.f("ix_user_game_follows_id"), table_name="user_game_follows")
    op.drop_table("user_game_follows")
    op.drop_index(
        "ix_user_game_alert_overrides_user_game", table_name="user_game_alert_overrides"
    )
    op.drop_index(
        op.f("ix_user_game_alert_overrides_id"), table_name="user_game_alert_overrides"
    )
    op.drop_table("user_game_alert_overrides")
    op.drop_index(op.f("ix_game_odds_current_id"), table_name="game_odds_current")
    op.drop_table("game_odds_current")
    op.drop_index(op.f("ix_alerts_user_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_triggered_at"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_game_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_user_team_follows_id"), table_name="user_team_follows")
    op.drop_table("user_team_follows")
    op.drop_index(
        op.f("ix_user_alert_preferences_id"), table_name="user_alert_preferences"
    )
    op.drop_table("user_alert_preferences")
    op.drop_index(
        op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions"
    )
    op.drop_index(op.f("ix_push_subscriptions_id"), table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_index(op.f("ix_games_id"), table_name="games")
    op.drop_index("ix_games_competition_is_final_status_sched", table_name="games")
    op.drop_table("games")
    op.drop_table("competition_teams")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_teams_sport"), table_name="teams")
    op.drop_index(op.f("ix_teams_id"), table_name="teams")
    op.drop_table("teams")
    op.drop_table("odds_api_daily_usage")
    op.drop_index(
        op.f("ix_email_login_tokens_token_hash"), table_name="email_login_tokens"
    )
    op.drop_index(op.f("ix_email_login_tokens_id"), table_name="email_login_tokens")
    op.drop_index(
        op.f("ix_email_login_tokens_expires_at"), table_name="email_login_tokens"
    )
    op.drop_index(op.f("ix_email_login_tokens_email"), table_name="email_login_tokens")
    op.drop_index(
        op.f("ix_email_login_tokens_created_at"), table_name="email_login_tokens"
    )
    op.drop_index(
        op.f("ix_email_login_tokens_consumed_at"), table_name="email_login_tokens"
    )
    op.drop_table("email_login_tokens")
    op.drop_index(
        op.f("ix_competition_settings_is_enabled"), table_name="competition_settings"
    )
    op.drop_table("competition_settings")
