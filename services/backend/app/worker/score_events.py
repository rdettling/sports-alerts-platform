from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.db.models import Game
from app.worker.scoreboard import ScoreboardGame


Leader = Literal["away", "home", "tied"]


@dataclass(frozen=True)
class ScoreChangeEvent:
    previous_home_score: int
    previous_away_score: int
    new_home_score: int
    new_away_score: int
    scoring_side: str | None
    is_inferred_goal: bool
    previous_leader: Leader
    new_leader: Leader
    period: int | None
    clock: str | None
    status: str

    @property
    def lead_changed(self) -> bool:
        opening_score = self.previous_home_score == 0 and self.previous_away_score == 0
        return not opening_score and self.previous_leader != self.new_leader


def _leader(home_score: int, away_score: int) -> Leader:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "tied"


def classify_score_change(
    previous: Game,
    payload: ScoreboardGame,
    *,
    sport: str,
) -> ScoreChangeEvent | None:
    live_statuses = {"in_progress", "live"}
    if payload.is_final or payload.status not in live_statuses:
        return None
    if sport == "soccer" and (payload.period or 0) >= 5:
        return None
    if (
        previous.home_score is None
        or previous.away_score is None
        or payload.home_score is None
        or payload.away_score is None
    ):
        return None

    home_delta = payload.home_score - previous.home_score
    away_delta = payload.away_score - previous.away_score
    if home_delta < 0 or away_delta < 0 or (home_delta == 0 and away_delta == 0):
        return None

    scoring_side: str | None = None
    if home_delta > 0 and away_delta == 0:
        scoring_side = "home"
    elif away_delta > 0 and home_delta == 0:
        scoring_side = "away"

    return ScoreChangeEvent(
        previous_home_score=previous.home_score,
        previous_away_score=previous.away_score,
        new_home_score=payload.home_score,
        new_away_score=payload.away_score,
        scoring_side=scoring_side,
        is_inferred_goal=(
            sport == "soccer"
            and ((home_delta == 1 and away_delta == 0) or (away_delta == 1 and home_delta == 0))
        ),
        previous_leader=_leader(previous.home_score, previous.away_score),
        new_leader=_leader(payload.home_score, payload.away_score),
        period=payload.period,
        clock=payload.clock,
        status=payload.status,
    )
