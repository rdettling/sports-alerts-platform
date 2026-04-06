from pydantic import BaseModel, Field

ALERT_TYPES = ["game_start", "close_game_late", "final_result"]


class AlertPreferenceOut(BaseModel):
    alert_type: str
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None

    model_config = {"from_attributes": True}


class UpdateAlertPreferenceRequest(BaseModel):
    is_enabled: bool | None = None
    close_game_margin_threshold: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds: int | None = Field(default=None, ge=0, le=3600)

