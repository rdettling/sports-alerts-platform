from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://sports:sports@localhost:5432/sports_alerts"
    worker_poll_interval_seconds: int = 60
    worker_poll_interval_live_seconds: int = 30
    worker_poll_interval_soon_seconds: int = 120
    worker_poll_interval_day_seconds: int = 300
    worker_poll_interval_idle_seconds: int = 900
    nba_provider: str = "espn"
    delivery_mode: str = "log"
    from_email: str = "alerts@sports-alerts.local"


settings = WorkerSettings()
