from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeliverySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    delivery_mode: Literal["live", "log"] = "live"
    from_email: str = "alerts@livegamealerts.com"
    resend_api_key: str
    resend_api_url: str = "https://api.resend.com/emails"


delivery_settings = DeliverySettings()
