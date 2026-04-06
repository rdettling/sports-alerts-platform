from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://sports:sports@localhost:5432/sports_alerts"
    worker_poll_interval_seconds: int = 60
    nba_provider: str = "espn"


settings = WorkerSettings()
