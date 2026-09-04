from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.usage import record_activity


class _DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str


database_settings = _DatabaseSettings()
engine = create_engine(database_settings.database_url, pool_pre_ping=True, poolclass=NullPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@event.listens_for(engine, "checkout")
def record_connection(*_args):
    record_activity("connections", database=True)


@event.listens_for(engine, "before_cursor_execute")
def record_statement(*_args):
    record_activity("statements", database=True)


@event.listens_for(engine, "commit")
def record_commit(*_args):
    record_activity("commits", database=True)


@event.listens_for(engine, "rollback")
def record_rollback(*_args):
    record_activity("rollbacks", database=True)


@event.listens_for(engine, "handle_error")
def record_error(*_args):
    record_activity("errors", database=True)
