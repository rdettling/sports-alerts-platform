from pydantic import BaseModel

from app.schemas.game import GameOut
from app.schemas.team import TeamOut


class LeagueFollowOut(BaseModel):
    league: str


class CurrentFollowsOut(BaseModel):
    leagues: list[LeagueFollowOut]
    teams: list[TeamOut]
    games: list[GameOut]
