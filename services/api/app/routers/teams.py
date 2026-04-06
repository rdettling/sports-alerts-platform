from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Team
from app.db.session import get_db
from app.schemas.team import TeamOut

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db)) -> list[TeamOut]:
    teams = db.scalars(select(Team).order_by(Team.name.asc())).all()
    return [TeamOut.model_validate(team) for team in teams]
