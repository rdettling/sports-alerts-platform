from pydantic import BaseModel, Field
from app.services.leagues import list_supported_leagues

ALERT_TYPES = ["game_start", "close_game_late", "inning_start", "final_result"]
SUPPORTED_LEAGUES = list_supported_leagues()


class AlertPreferenceOut(BaseModel):
    league: str
    alert_type: str
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None

    model_config = {"from_attributes": True}


class UpdateAlertPreferenceRequest(BaseModel):
    is_enabled: bool | None = None
    close_game_margin_threshold: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds: int | None = Field(default=None, ge=0, le=3600)
    inning_start_threshold: int | None = Field(default=None, ge=1, le=20)


class AlertPreferenceGroupOut(BaseModel):
    league: str
    preferences: list[AlertPreferenceOut]


class UpdateGameAlertOverrideRequest(BaseModel):
    is_enabled_override: bool | None = None
    close_game_margin_threshold_override: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds_override: int | None = Field(default=None, ge=0, le=3600)
    inning_start_threshold_override: int | None = Field(default=None, ge=1, le=20)


class GameAlertPreferenceItemOut(BaseModel):
    league: str
    alert_type: str
    use_league_default: bool
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    inning_start_threshold: int | None = None
    override: dict[str, int | bool | None] | None = None


class GameAlertPreferencesOut(BaseModel):
    game_id: int
    league: str
    items: list[GameAlertPreferenceItemOut]
