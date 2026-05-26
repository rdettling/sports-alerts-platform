from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "sports-alerts-api"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 86400
    magic_link_ttl_minutes: int = 15
    magic_link_cooldown_seconds: int = 60
    magic_link_max_requests_per_hour: int = 5
    web_base_url: str
    cors_allow_origins: str
    delivery_mode: str = "email"
    from_email: str = "alerts@livegamealerts.com"
    resend_api_key: str
    resend_api_url: str = "https://api.resend.com/emails"
    odds_api_key: str
    odds_api_base_url: str = "https://api.the-odds-api.com/v4/sports"
    odds_provider: str = "the_odds_api"
    odds_api_sport_key: str = "basketball_nba"
    odds_api_regions: str = "us"
    odds_api_market: str = "h2h"
    odds_api_format: str = "american"
    odds_api_timeout_seconds: int = 6
    odds_api_cache_seconds: int = 60
    odds_enabled: bool = False
    bootstrap_admin_email: str = "ryandettling1@gmail.com"
    neon_api_key: str = ""
    neon_project_id: str = ""
    neon_org_id: str = ""
    neon_dashboard_url: str = ""


settings = Settings()
