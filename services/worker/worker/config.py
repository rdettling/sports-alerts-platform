from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    worker_poll_interval_seconds: int
    worker_poll_interval_live_seconds: int
    worker_poll_interval_soon_seconds: int
    worker_poll_interval_day_seconds: int
    worker_poll_interval_idle_seconds: int
    nba_provider: str
    delivery_mode: str
    from_email: str
    resend_api_key: str
    resend_api_url: str


settings = WorkerSettings()
