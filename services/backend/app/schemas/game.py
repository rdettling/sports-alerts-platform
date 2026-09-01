from datetime import datetime

from pydantic import BaseModel, Field


class GameTeamOut(BaseModel):
    id: int
    sport: str
    external_team_id: str
    name: str
    abbreviation: str
    conference: str | None


class TeamStrengthOut(BaseModel):
    wins: int | None = None
    losses: int | None = None
    ties: int | None = None
    rank: int | None = None

    model_config = {"from_attributes": True}


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
    competition: str
    home_team_id: int
    away_team_id: int
    home_team: GameTeamOut
    away_team: GameTeamOut
    scheduled_start_time: datetime
    context_label: str | None
    home_team_strength: TeamStrengthOut = Field(default_factory=TeamStrengthOut)
    away_team_strength: TeamStrengthOut = Field(default_factory=TeamStrengthOut)
    broadcast_names: list[str]
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    is_final: bool
    last_ingested_at: datetime | None
    odds: GameOddsOut | None = None

    model_config = {"from_attributes": True}
