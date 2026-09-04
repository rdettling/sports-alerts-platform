from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    catalog_sync_interval_seconds: int = 43200
    odds_api_key: str = ""
    live_update_api_url: str = ""
    live_update_secret: str = ""


settings = WorkerSettings()
