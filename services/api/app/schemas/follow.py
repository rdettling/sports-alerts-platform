from pydantic import BaseModel

from app.schemas.game import GameOut
from app.schemas.team import TeamOut


class CurrentFollowsOut(BaseModel):
    teams: list[TeamOut]
    games: list[GameOut]

