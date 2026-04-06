from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team_follows = relationship("UserTeamFollow", back_populates="user")
    game_follows = relationship("UserGameFollow", back_populates="user")


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
    __table_args__ = (UniqueConstraint("external_game_id", "league", name="uq_games_external_league"),)

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
    clock: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class UserGameFollow(Base):
    __tablename__ = "user_game_follows"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_user_game_follows_user_game"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="game_follows")
    game = relationship("Game")


class UserAlertPreference(Base):
    __tablename__ = "user_alert_preferences"
    __table_args__ = (UniqueConstraint("user_id", "alert_type", name="uq_user_alert_preferences_user_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    alert_type: Mapped[str] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    close_game_margin_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_game_time_threshold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    games_checked: Mapped[int] = mapped_column(Integer, default=0)
    games_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
