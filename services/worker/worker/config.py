from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    catalog_sync_interval_seconds: int = 43200
    live_sync_interval_seconds: int = 120
    nba_live_sync_interval_seconds: int = 120
    mlb_live_sync_interval_seconds: int = 300
    odds_pregame_window_hours: int = 24
    ingest_live_interval_seconds: int = 120
    ingest_pregame_hot_interval_seconds: int = 900
    ingest_pregame_cold_interval_seconds: int = 3600
    ingest_off_interval_seconds: int = 43200
    ingest_pregame_hot_window_minutes: int = 90
    ingest_pregame_cold_window_hours: int = 24
    ingest_cold_start_lookback_days: int = 2
    ingest_cold_start_lookahead_days: int = 7
    ingest_heartbeat_seconds: int = 3600
    scheduler_max_sleep_seconds: int = 300
    delivery_empty_backoff_seconds: int = 900
    delivery_active_backoff_seconds: int = 120
    delivery_live_fast_backoff_seconds: int = 60
    delivery_live_fast_window_seconds: int = 600
    cleanup_interval_seconds: int = 21600
    games_retention_past_hours: int = 36
    games_retention_future_days: int = 7
    job_max_retries: int = 5
    job_retry_base_seconds: int = 30
    job_retry_max_backoff_seconds: int = 3600
    telemetry_raw_events_enabled: bool = False
    nba_provider: str = "espn"
    odds_provider: str = "the_odds_api"
    odds_api_key: str
    odds_api_base_url: str = "https://api.the-odds-api.com/v4/sports"
    odds_api_sport_key: str = "basketball_nba"
    odds_api_sport_key_nba: str = "basketball_nba"
    odds_api_sport_key_mlb: str = "baseball_mlb"
    odds_api_regions: str = "us"
    odds_api_market: str = "h2h"
    odds_api_format: str = "american"
    odds_api_timeout_seconds: int = 6
    odds_api_cache_seconds: int = 60
    odds_enabled: bool = True
    odds_refresh_seconds: int = 21600
    delivery_mode: str = "email"
    from_email: str = "alerts@livegamealerts.com"
    resend_api_key: str
    resend_api_url: str = "https://api.resend.com/emails"


settings = WorkerSettings()
