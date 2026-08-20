from pydantic import BaseModel, Field
from app.services.competitions import list_supported_sports

SUPPORTED_SPORTS = list_supported_sports()


class AlertSettingsOut(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None


class AlertPreferenceOut(AlertSettingsOut):
    sport: str
    alert_type: str

    model_config = {"from_attributes": True}


class UpdateAlertSettingsRequest(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds: int | None = Field(default=None, ge=0, le=3600)
    inning_start_threshold: int | None = Field(default=None, ge=1, le=20)

    model_config = {"extra": "forbid"}


class AlertPreferenceGroupOut(BaseModel):
    sport: str
    preferences: list[AlertPreferenceOut]


class GameAlertPreferenceItemOut(AlertPreferenceOut):
    uses_sport_defaults: bool


class GameAlertPreferencesOut(BaseModel):
    game_id: int
    competition: str
    sport: str
    items: list[GameAlertPreferenceItemOut]
