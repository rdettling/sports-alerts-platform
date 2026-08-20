from pydantic import BaseModel


class CompetitionSettingOut(BaseModel):
    competition: str
    sport: str
    label: str
    badge_label: str
    alert_types: list[str]
    live_sync_interval_seconds: int
    is_enabled: bool


class UpdateCompetitionSettingRequest(BaseModel):
    is_enabled: bool
