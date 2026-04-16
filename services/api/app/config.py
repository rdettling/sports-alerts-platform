from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str
    api_host: str
    api_port: int
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    magic_link_ttl_minutes: int
    magic_link_cooldown_seconds: int
    magic_link_max_requests_per_hour: int
    web_base_url: str
    cors_allow_origins: str
    delivery_mode: str
    from_email: str
    resend_api_key: str
    resend_api_url: str
    odds_api_key: str
    odds_api_base_url: str
    odds_provider: str
    odds_api_sport_key: str
    odds_api_regions: str
    odds_api_market: str
    odds_api_format: str
    odds_api_timeout_seconds: int
    odds_api_cache_seconds: int
    odds_enabled: bool
    odds_refresh_seconds: int
settings = Settings()
