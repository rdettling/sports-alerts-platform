from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    ingest_interval_active_seconds: int = 300
    ingest_interval_idle_seconds: int = 3600
    scheduler_max_sleep_seconds: int = 60
    ingest_freshness_target_seconds: int = 60
    delivery_empty_backoff_seconds: int = 300
    delivery_active_backoff_seconds: int = 30
    cleanup_interval_seconds: int = 1800
    games_retention_past_hours: int = 36
    games_retention_future_days: int = 7
    job_max_retries: int = 5
    job_retry_base_seconds: int = 30
    telemetry_raw_events_enabled: bool = False
    nba_provider: str = "espn"
    odds_provider: str = "the_odds_api"
    odds_api_key: str
    odds_api_base_url: str = "https://api.the-odds-api.com/v4/sports"
    odds_api_sport_key: str = "basketball_nba"
    odds_api_regions: str = "us"
    odds_api_market: str = "h2h"
    odds_api_format: str = "american"
    odds_api_timeout_seconds: int = 6
    odds_api_cache_seconds: int = 60
    odds_enabled: bool = False
    odds_refresh_seconds: int = 5400
    delivery_mode: str = "log"
    from_email: str = "alerts@livegamealerts.com"
    resend_api_key: str
    resend_api_url: str = "https://api.resend.com/emails"


settings = WorkerSettings()
