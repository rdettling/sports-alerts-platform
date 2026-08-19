from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "sports-alerts-api"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 86400
    magic_link_ttl_minutes: int = 15
    magic_link_cooldown_seconds: int = 60
    magic_link_max_requests_per_hour: int = 5
    web_base_url: str
    cors_allow_origins: str
    odds_provider: str = "the_odds_api"
    odds_api_market: str = "h2h"
    bootstrap_admin_email: str = "ryandettling1@gmail.com"
    neon_api_key: str = ""
    neon_project_id: str = ""
    neon_org_id: str = ""
    neon_dashboard_url: str = ""


settings = Settings()
