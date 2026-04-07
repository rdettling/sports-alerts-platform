from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "sports-alerts-api"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://sports:sports@localhost:5432/sports_alerts"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_allow_origins: str = "http://localhost:5173"
    odds_api_key: str | None = None
    odds_api_base_url: str = "https://api.the-odds-api.com/v4/sports"
    odds_provider: str = "the_odds_api"
    odds_api_sport_key: str = "basketball_nba"
    odds_api_regions: str = "us"
    odds_api_market: str = "h2h"
    odds_api_format: str = "american"
    odds_api_timeout_seconds: int = 6
    odds_api_cache_seconds: int = 60
    dev_mode: bool = False


settings = Settings()
