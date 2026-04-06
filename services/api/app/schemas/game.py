from datetime import datetime

from pydantic import BaseModel


class GameOut(BaseModel):
    id: int
    external_game_id: str
    league: str
    home_team_id: int
    away_team_id: int
    scheduled_start_time: datetime
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    is_final: bool

    model_config = {"from_attributes": True}
