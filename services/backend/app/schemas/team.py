from pydantic import BaseModel


class TeamOut(BaseModel):
    id: int
    external_team_id: str
    league: str
    name: str
    abbreviation: str

    model_config = {"from_attributes": True}
