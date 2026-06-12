from pydantic import BaseModel


class LeagueSettingOut(BaseModel):
    league: str
    is_enabled: bool

    model_config = {"from_attributes": True}


class UpdateLeagueSettingRequest(BaseModel):
    is_enabled: bool
