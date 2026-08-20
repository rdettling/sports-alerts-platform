from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompetitionTeam, Team
from app.db.session import get_db
from app.schemas.team import TeamOut, build_team_out
from app.services.competitions import get_active_competitions

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db)) -> list[TeamOut]:
    rows = db.execute(
        select(Team, CompetitionTeam.competition)
        .join(CompetitionTeam, CompetitionTeam.team_id == Team.id)
        .where(CompetitionTeam.competition.in_(get_active_competitions(db)))
        .order_by(Team.name.asc(), CompetitionTeam.competition.asc())
    ).all()
    teams: dict[int, TeamOut] = {}
    for team, competition in rows:
        item = teams.get(team.id)
        if item is None:
            item = build_team_out(team, [])
            teams[team.id] = item
        item.competitions.append(competition)
    return list(teams.values())
