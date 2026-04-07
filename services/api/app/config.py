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
    cors_allow_origins: str
    odds_api_key: str
    odds_api_base_url: str
    odds_provider: str
    odds_api_sport_key: str
    odds_api_regions: str
    odds_api_market: str
    odds_api_format: str
    odds_api_timeout_seconds: int
    odds_api_cache_seconds: int
    dev_mode: bool


settings = Settings()
