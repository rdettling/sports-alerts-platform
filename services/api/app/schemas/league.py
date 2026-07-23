from pydantic import BaseModel


class LeagueSettingOut(BaseModel):
    league: str
    sport: str
    label: str
    badge_label: str
    alert_types: list[str]
    live_sync_interval_seconds: int
    is_enabled: bool


class UpdateLeagueSettingRequest(BaseModel):
    is_enabled: bool
