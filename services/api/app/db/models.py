from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(Enum("user", "admin", name="user_role"), default="user", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team_follows = relationship("UserTeamFollow", back_populates="user")
    league_follows = relationship("UserLeagueFollow", back_populates="user")
    game_follows = relationship("UserGameFollow", back_populates="user")
    game_unfollows = relationship("UserGameUnfollow", back_populates="user")
    alert_defaults = relationship("UserAlertDefault", back_populates="user")
    game_alert_overrides = relationship("UserGameAlertOverride", back_populates="user")


class EmailLoginToken(Base):
    __tablename__ = "email_login_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
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
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clock: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
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
    home_moneyline: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_moneyline: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bookmaker: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserTeamFollow(Base):
    __tablename__ = "user_team_follows"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_user_team_follows_user_team"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="team_follows")
    team = relationship("Team")


class UserLeagueFollow(Base):
    __tablename__ = "user_league_follows"
    __table_args__ = (UniqueConstraint("user_id", "league", name="uq_user_league_follows_user_league"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    league: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="league_follows")


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


class UserAlertDefault(Base):
    __tablename__ = "user_alert_defaults"
    __table_args__ = (UniqueConstraint("user_id", "league", "alert_type", name="uq_user_alert_defaults_user_league_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    league: Mapped[str] = mapped_column(String(16))
    alert_type: Mapped[str] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    close_game_margin_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_game_time_threshold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inning_start_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="alert_defaults")


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


class SentAlert(Base):
    __tablename__ = "sent_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    alert_type: Mapped[str] = mapped_column(String(32))
    delivery_channel: Mapped[str] = mapped_column(String(32))
    delivery_status: Mapped[str] = mapped_column(String(32))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


Index("ix_sent_alerts_delivery_status_sent_at", SentAlert.delivery_status, SentAlert.sent_at)


class SportsUpdateSourceItem(Base):
    __tablename__ = "sports_update_source_items"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_sports_update_source_items_dedupe_key"),
        Index("ix_sports_update_source_items_league_published", "league", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(16), default="rss", index=True)
    source_name: Mapped[str] = mapped_column(String(80))
    feed_key: Mapped[str] = mapped_column(String(32), index=True)
    league: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_url: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(128))
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SportsUpdate(Base):
    __tablename__ = "sports_updates"
    __table_args__ = (
        UniqueConstraint("source_item_id", name="uq_sports_updates_source_item"),
        Index("ix_sports_updates_status_created", "classifier_status", "created_at"),
        Index("ix_sports_updates_scope_league", "scope", "league"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_item_id: Mapped[int] = mapped_column(ForeignKey("sports_update_source_items.id"))
    league: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    scope: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    importance: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classifier_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    classifier_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source_item = relationship("SportsUpdateSourceItem")


class SportsUpdateTeam(Base):
    __tablename__ = "sports_update_teams"
    __table_args__ = (
        UniqueConstraint("sports_update_id", "team_id", name="uq_sports_update_teams_update_team"),
        Index("ix_sports_update_teams_team", "team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sports_update_id: Mapped[int] = mapped_column(ForeignKey("sports_updates.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    sports_update = relationship("SportsUpdate")
    team = relationship("Team")


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
