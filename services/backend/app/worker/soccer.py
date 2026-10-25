from __future__ import annotations

import logging
from dataclasses import dataclass

from app.db.models import Game
from app.worker.period_events import is_soccer_extra_time, is_soccer_second_half
from app.worker.score_events import ScoreChangeEvent
from app.worker.scoreboard import ScoreboardGame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StateSnapshot:
    external_game_id: str
    context_label: str | None
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    is_final: bool


def is_penalty_kicks_window(
    *,
    status: str,
    period: int | None,
    home_score: int | None,
    away_score: int | None,
    clock: str | None,
) -> bool:
    if status not in {"in_progress", "live"}:
        return False
    if home_score is None or away_score is None or home_score != away_score:
        return False
    if (period or 0) >= 5:
        return True
    if not is_soccer_extra_time(status=status, period=period) or not clock:
        return False
    minute_text = clock.strip().replace("'", "").split("+", 1)[0].strip()
    try:
        return bool(minute_text) and int(minute_text) >= 117
    except ValueError:
        return False


def snapshot_state(game: Game) -> StateSnapshot:
    return StateSnapshot(
        external_game_id=game.external_game_id,
        context_label=game.context_label,
        status=game.status,
        home_score=game.home_score,
        away_score=game.away_score,
        period=game.period,
        clock=game.clock,
        is_final=game.is_final,
    )


def log_transition(
    previous: StateSnapshot,
    payload: ScoreboardGame,
    *,
    score_change: ScoreChangeEvent | None,
    period_start_type: str | None,
) -> None:
    previous_second_half = is_soccer_second_half(status=previous.status, period=previous.period, clock=previous.clock)
    new_second_half = is_soccer_second_half(status=payload.status, period=payload.period, clock=payload.clock)
    previous_extra_time = is_soccer_extra_time(status=previous.status, period=previous.period)
    new_extra_time = is_soccer_extra_time(status=payload.status, period=payload.period)
    previous_penalty_kicks_window = is_penalty_kicks_window(
        status=previous.status,
        period=previous.period,
        home_score=previous.home_score,
        away_score=previous.away_score,
        clock=previous.clock,
    )
    new_penalty_kicks_window = is_penalty_kicks_window(
        status=payload.status,
        period=payload.period,
        home_score=payload.home_score,
        away_score=payload.away_score,
        clock=payload.clock,
    )

    logger.info(
        "Soccer state transition external_game_id=%s status=%s->%s period=%s->%s clock=%r->%r "
        "score=%s-%s->%s-%s is_final=%s->%s second_half_live=%s->%s extra_time=%s->%s "
        "penalty_kicks_window=%s->%s second_half_started=%s extra_time_started=%s score_changed=%s scoring_side=%s inferred_goal=%s context_label=%r->%r",
        previous.external_game_id,
        previous.status,
        payload.status,
        previous.period,
        payload.period,
        previous.clock,
        payload.clock,
        previous.away_score,
        previous.home_score,
        payload.away_score,
        payload.home_score,
        previous.is_final,
        payload.is_final,
        previous_second_half,
        new_second_half,
        previous_extra_time,
        new_extra_time,
        previous_penalty_kicks_window,
        new_penalty_kicks_window,
        period_start_type == "second_half_start",
        period_start_type == "extra_time_start",
        score_change is not None,
        score_change.scoring_side if score_change is not None else None,
        score_change.is_inferred_goal if score_change is not None else False,
        previous.context_label,
        payload.context_label,
    )
