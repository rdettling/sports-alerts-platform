from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    catalog_sync_interval_seconds: int = 43200
    odds_api_key: str = ""
    scheduler_idle_max_sleep_seconds: int = 3600


settings = WorkerSettings()
