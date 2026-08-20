from pydantic import BaseModel, Field
from app.services.leagues import list_supported_leagues

SUPPORTED_LEAGUES = list_supported_leagues()


class AlertSettingsOut(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None


class AlertPreferenceOut(AlertSettingsOut):
    league: str
    alert_type: str

    model_config = {"from_attributes": True}


class UpdateAlertSettingsRequest(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds: int | None = Field(default=None, ge=0, le=3600)
    inning_start_threshold: int | None = Field(default=None, ge=1, le=20)

    model_config = {"extra": "forbid"}


class AlertPreferenceGroupOut(BaseModel):
    league: str
    preferences: list[AlertPreferenceOut]


class GameAlertPreferenceItemOut(AlertPreferenceOut):
    uses_league_defaults: bool


class GameAlertPreferencesOut(BaseModel):
    game_id: int
    league: str
    items: list[GameAlertPreferenceItemOut]
