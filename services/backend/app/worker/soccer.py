from __future__ import annotations

import logging
from dataclasses import dataclass

from app.db.models import Game
from app.worker.score_events import ScoreChangeEvent, classify_score_change
from app.worker.scoreboard import ScoreboardGame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SoccerDerivedEvents:
    score_change: ScoreChangeEvent | None = None
    second_half_started: bool = False
    extra_time_started: bool = False


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


def _is_live_second_half(*, status: str, period: int | None, clock: str | None) -> bool:
    if status not in {"in_progress", "live"} or period != 2:
        return False
    return (clock or "").strip().upper() not in {"HT", "HALFTIME"}


def _is_extra_time(*, status: str, period: int | None) -> bool:
    return status in {"in_progress", "live"} and period in {3, 4}


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
    if not _is_extra_time(status=status, period=period) or not clock:
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


def classify_events(previous: Game | None, payload: ScoreboardGame) -> SoccerDerivedEvents | None:
    if previous is None:
        return None
    score_change = classify_score_change(previous, payload, sport="soccer")

    second_half_started = (
        not payload.is_final
        and not _is_live_second_half(status=previous.status, period=previous.period, clock=previous.clock)
        and _is_live_second_half(status=payload.status, period=payload.period, clock=payload.clock)
    )
    extra_time_started = (
        not payload.is_final
        and not _is_extra_time(status=previous.status, period=previous.period)
        and _is_extra_time(status=payload.status, period=payload.period)
    )
    if score_change is None and not second_half_started and not extra_time_started:
        return None
    return SoccerDerivedEvents(
        score_change=score_change,
        second_half_started=second_half_started,
        extra_time_started=extra_time_started,
    )


def log_transition(previous: StateSnapshot, payload: ScoreboardGame, events: SoccerDerivedEvents | None) -> None:
    previous_second_half = _is_live_second_half(status=previous.status, period=previous.period, clock=previous.clock)
    new_second_half = _is_live_second_half(status=payload.status, period=payload.period, clock=payload.clock)
    previous_extra_time = _is_extra_time(status=previous.status, period=previous.period)
    new_extra_time = _is_extra_time(status=payload.status, period=payload.period)
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
    score_change = events.score_change if events is not None else None

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
        events.second_half_started if events is not None else False,
        events.extra_time_started if events is not None else False,
        score_change is not None,
        score_change.scoring_side if score_change is not None else None,
        score_change.is_inferred_goal if score_change is not None else False,
        previous.context_label,
        payload.context_label,
    )
