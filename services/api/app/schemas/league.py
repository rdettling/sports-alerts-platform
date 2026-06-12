from pydantic import BaseModel


class LeagueSettingOut(BaseModel):
    league: str
    label: str
    badge_label: str
    alert_types: list[str]
    is_enabled: bool


class UpdateLeagueSettingRequest(BaseModel):
    is_enabled: bool
