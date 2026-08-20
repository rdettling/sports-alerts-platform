from pydantic import BaseModel

from app.db.models import Team


class TeamOut(BaseModel):
    id: int
    sport: str
    external_team_id: str
    name: str
    abbreviation: str
    competitions: list[str]


def build_team_out(team: Team, competitions: list[str]) -> TeamOut:
    return TeamOut(
        id=team.id,
        sport=team.sport,
        external_team_id=team.external_team_id,
        name=team.name,
        abbreviation=team.abbreviation,
        competitions=competitions,
    )
