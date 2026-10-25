from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class AlertSettingsOut(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = None
    close_game_time_threshold_seconds: int | None = None
    periods: list[int] | None = None


class AlertPreferenceOut(AlertSettingsOut):
    competition: str
    alert_type: str

    model_config = {"from_attributes": True}


class UpdateAlertSettingsRequest(BaseModel):
    is_enabled: bool
    close_game_margin_threshold: int | None = Field(default=None, ge=0, le=50)
    close_game_time_threshold_seconds: int | None = Field(default=None, ge=0, le=3600)
    periods: list[Annotated[int, Field(strict=True, ge=1, le=9)]] | None = None

    @field_validator("periods")
    @classmethod
    def normalize_periods(cls, periods: list[int] | None) -> list[int] | None:
        return sorted(set(periods)) if periods is not None else None

    model_config = {"extra": "forbid"}


class AlertPreferenceGroupOut(BaseModel):
    competition: str
    label: str
    preferences: list[AlertPreferenceOut]


class GameAlertPreferenceItemOut(AlertPreferenceOut):
    uses_league_defaults: bool


class GameAlertPreferencesOut(BaseModel):
    game_id: int
    competition: str
    items: list[GameAlertPreferenceItemOut]
