from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    catalog_sync_interval_seconds: int = 43200
    nba_live_sync_interval_seconds: int = 120
    mlb_live_sync_interval_seconds: int = 300
    world_cup_live_sync_interval_seconds: int = 180
    odds_pregame_window_hours: int = 24
    odds_provider: str = "the_odds_api"
    odds_api_key: str
    odds_api_base_url: str = "https://api.the-odds-api.com/v4/sports"
    odds_api_sport_key_nba: str = "basketball_nba"
    odds_api_sport_key_mlb: str = "baseball_mlb"
    odds_api_sport_key_world_cup: str = "soccer_fifa_world_cup"
    odds_api_regions: str = "us"
    odds_api_market: str = "h2h"
    odds_api_format: str = "american"
    odds_api_timeout_seconds: int = 6
    odds_api_cache_seconds: int = 60
    odds_enabled: bool = True
    scheduler_tick_seconds: int = 15
    scheduler_idle_max_sleep_seconds: int = 3600
    openai_api_key: str = ""
    openai_api_base_url: str = "https://api.openai.com/v1"


settings = WorkerSettings()
