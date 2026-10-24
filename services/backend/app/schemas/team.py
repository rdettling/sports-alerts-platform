from pydantic import BaseModel

from app.db.models import Team
from app.services.team_catalog import TEAM_CONFERENCES_BY_SCOPE


class TeamOut(BaseModel):
    id: int
    sport: str
    external_team_id: str
    name: str
    abbreviation: str
    competitions: list[str]
    conference: str | None


def build_team_out(team: Team, competitions: list[str]) -> TeamOut:
    return TeamOut(
        id=team.id,
        sport=team.sport,
        external_team_id=team.external_team_id,
        name=team.name,
        abbreviation=team.abbreviation,
        competitions=competitions,
        conference=(
            TEAM_CONFERENCES_BY_SCOPE.get(team.provider_scope, {}).get(team.external_team_id)
        ),
    )
