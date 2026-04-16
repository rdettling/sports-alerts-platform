from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    ingest_interval_live_seconds: int
    ingest_interval_active_seconds: int
    ingest_interval_idle_seconds: int
    delivery_tick_seconds: int
    nba_provider: str
    odds_provider: str
    odds_api_key: str
    odds_api_base_url: str
    odds_api_sport_key: str
    odds_api_regions: str
    odds_api_market: str
    odds_api_format: str
    odds_api_timeout_seconds: int
    odds_api_cache_seconds: int
    odds_enabled: bool
    odds_refresh_seconds: int
    delivery_mode: str
    from_email: str
    resend_api_key: str
    resend_api_url: str


settings = WorkerSettings()
