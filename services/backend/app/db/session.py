from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


class _DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{Path.home() / '.local/share/sports-alerts/sports-alerts.db'}"


database_settings = _DatabaseSettings()
url = make_url(database_settings.database_url)
if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
    raise ValueError("DATABASE_URL must point to a local SQLite file")
database_path = Path(url.database).resolve()
database_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    url,
    connect_args={"timeout": 30, "check_same_thread": False},
    pool_size=5,
    max_overflow=0,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


@event.listens_for(engine, "connect")
def configure_sqlite(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db():
    with SessionLocal() as db:
        yield db
