from pydantic import BaseModel


class CompetitionVisibilityOut(BaseModel):
    hidden_competitions: list[str]


class UpdateCompetitionVisibilityRequest(BaseModel):
    hidden_competitions: list[str]

    model_config = {"extra": "forbid"}
