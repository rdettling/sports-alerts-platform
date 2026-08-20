from datetime import datetime

from pydantic import BaseModel


class GameOddsOutcomeOut(BaseModel):
    outcome_key: str
    outcome_label: str
    price_american: int | None
    team_side: str | None


class GameOddsOut(BaseModel):
    bookmaker: str | None
    last_update: datetime | None
    outcomes: list[GameOddsOutcomeOut]


class GameOut(BaseModel):
    id: int
    external_game_id: str
    league: str
    home_team_id: int
    away_team_id: int
    scheduled_start_time: datetime
    context_label: str | None
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    is_final: bool
    last_ingested_at: datetime | None
    odds: GameOddsOut | None = None

    model_config = {"from_attributes": True}
