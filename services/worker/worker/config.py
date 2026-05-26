from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    catalog_sync_interval_seconds: int = 43200
    nba_live_sync_interval_seconds: int = 120
    mlb_live_sync_interval_seconds: int = 300
    live_sync_pregame_retry_seconds: int = 600
    odds_pregame_window_hours: int = 24
    nba_provider: str = "espn"
    odds_provider: str = "the_odds_api"
    odds_api_key: str
    odds_api_sport_key_nba: str = "basketball_nba"
    odds_api_sport_key_mlb: str = "baseball_mlb"
    odds_api_market: str = "h2h"
    odds_enabled: bool = True
    delivery_mode: str = "email"
    from_email: str = "alerts@livegamealerts.com"
    resend_api_key: str
    resend_api_url: str = "https://api.resend.com/emails"


settings = WorkerSettings()
