from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "alert_delivery_mode IN ('email', 'push', 'both')",
            name="ck_users_alert_delivery_mode",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(Enum("user", "admin", name="user_role"), default="user", index=True)
    alert_delivery_mode: Mapped[str] = mapped_column(String(16), default="email", server_default="email")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team_follows = relationship("UserTeamFollow", back_populates="user")
    game_follows = relationship("UserGameFollow", back_populates="user")
    game_unfollows = relationship("UserGameUnfollow", back_populates="user")
    alert_preferences = relationship("UserAlertPreference", back_populates="user")
    game_alert_overrides = relationship("UserGameAlertOverride", back_populates="user")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")


class EmailLoginToken(Base):
    __tablename__ = "email_login_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    failed_code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("external_team_id", "league", name="uq_teams_external_league"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_team_id: Mapped[str] = mapped_column(String(64))
    league: Mapped[str] = mapped_column(String(16), default="NBA")
    name: Mapped[str] = mapped_column(String(120))
    abbreviation: Mapped[str] = mapped_column(String(10))


class LeagueSetting(Base):
    __tablename__ = "league_settings"

    league: Mapped[str] = mapped_column(String(16), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("external_game_id", "league", name="uq_games_external_league"),
        Index("ix_games_league_is_final_status_sched", "league", "is_final", "status", "scheduled_start_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_game_id: Mapped[str] = mapped_column(String(64))
    league: Mapped[str] = mapped_column(String(16), default="NBA")
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    scheduled_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clock: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GameOddsCurrent(Base):
    __tablename__ = "game_odds_current"
    __table_args__ = (UniqueConstraint("game_id", "provider", "market", name="uq_game_odds_current_game_provider_market"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="the_odds_api")
    market: Mapped[str] = mapped_column(String(16), default="h2h")
    bookmaker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    outcomes = relationship("GameOddsOutcomeCurrent", back_populates="odds", cascade="all, delete-orphan", order_by="GameOddsOutcomeCurrent.outcome_order")


class GameOddsOutcomeCurrent(Base):
    __tablename__ = "game_odds_outcomes_current"
    __table_args__ = (
        UniqueConstraint("odds_id", "outcome_key", name="uq_game_odds_outcomes_current_odds_outcome_key"),
        UniqueConstraint("odds_id", "outcome_order", name="uq_game_odds_outcomes_current_odds_outcome_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    odds_id: Mapped[int] = mapped_column(ForeignKey("game_odds_current.id", ondelete="CASCADE"), index=True)
    outcome_key: Mapped[str] = mapped_column(String(32))
    outcome_label: Mapped[str] = mapped_column(String(80))
    outcome_order: Mapped[int] = mapped_column(Integer)
    price_american: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    odds = relationship("GameOddsCurrent", back_populates="outcomes")


class UserTeamFollow(Base):
    __tablename__ = "user_team_follows"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_user_team_follows_user_team"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="team_follows")
    team = relationship("Team")


class UserGameFollow(Base):
    __tablename__ = "user_game_follows"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_user_game_follows_user_game"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="game_follows")
    game = relationship("Game")


class UserGameUnfollow(Base):
    __tablename__ = "user_game_unfollows"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_user_game_unfollows_user_game"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="game_unfollows")
    game = relationship("Game")


class UserAlertPreference(Base):
    __tablename__ = "user_alert_preferences"
    __table_args__ = (UniqueConstraint("user_id", "league", "alert_type", name="uq_user_alert_preferences_user_league_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    league: Mapped[str] = mapped_column(String(16))
    alert_type: Mapped[str] = mapped_column(String(32))
    is_enabled_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    close_game_margin_threshold_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_game_time_threshold_seconds_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inning_start_threshold_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="alert_preferences")


class UserGameAlertOverride(Base):
    __tablename__ = "user_game_alert_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "game_id", "alert_type", name="uq_user_game_alert_overrides_user_game_type"),
        Index("ix_user_game_alert_overrides_user_game", "user_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    alert_type: Mapped[str] = mapped_column(String(32))
    is_enabled_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    close_game_margin_threshold_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_game_time_threshold_seconds_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inning_start_threshold_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="game_alert_overrides")
    game = relationship("Game")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(32))
    event_key: Mapped[str] = mapped_column(String(255), unique=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    deliveries = relationship("AlertDelivery", back_populates="alert", cascade="all, delete-orphan")


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    __table_args__ = (
        UniqueConstraint("alert_id", "channel", name="uq_alert_deliveries_alert_channel"),
        Index("ix_alert_deliveries_channel_attempted_at", "channel", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    alert = relationship("Alert", back_populates="deliveries")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="push_subscriptions")


class ApiCallRollupHourly(Base):
    __tablename__ = "api_call_rollups_hourly"
    __table_args__ = (
        UniqueConstraint(
            "bucket_start",
            "service",
            "provider",
            "endpoint_key",
            "attempt_status",
            name="uq_api_call_rollups_hourly_bucket_dims",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    service: Mapped[str] = mapped_column(String(16), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    endpoint_key: Mapped[str] = mapped_column(String(64), index=True)
    attempt_status: Mapped[str] = mapped_column(String(32), index=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)


class WorkerJob(Base):
    __tablename__ = "worker_jobs"
    __table_args__ = (
        UniqueConstraint("job_type", "league", name="uq_worker_jobs_job_type_league"),
        Index("ix_worker_jobs_status_next_run", "status", "next_run_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    league: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
