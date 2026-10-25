from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.db.models import Game
from app.services.competitions import get_competition_profile
from app.worker.scoreboard import ScoreboardGame


@dataclass(frozen=True)
class PeriodStartEvent:
    alert_type: str
    previous_observed_at: datetime


def is_soccer_second_half(
    *, status: str, period: int | None, clock: str | None
) -> bool:
    if status not in {"in_progress", "live"} or period != 2:
        return False
    return (clock or "").strip().upper() not in {"HT", "HALFTIME"}


def is_soccer_extra_time(*, status: str, period: int | None) -> bool:
    return status in {"in_progress", "live"} and period in {3, 4}


def _has_time_remaining(clock: str | None) -> bool:
    parts = (clock or "").strip().split(":")
    try:
        return len(parts) == 2 and float(parts[0]) * 60 + float(parts[1]) > 0
    except ValueError:
        return False


def classify_period_start(
    previous: Game, payload: ScoreboardGame
) -> PeriodStartEvent | None:
    profile = get_competition_profile(previous.competition)
    if (
        previous.is_final
        or payload.is_final
        or payload.status not in {"in_progress", "live"}
        or previous.last_ingested_at is None
    ):
        return None

    if profile.sport == "baseball":
        period = payload.period or 0
        is_top = (payload.clock or "").strip().lower().startswith("top ")
        was_top = (previous.clock or "").strip().lower().startswith("top ")
        if (
            1 <= period <= 9
            and (previous.period or 0) in {period - 1, period}
            and previous.status in {"scheduled", "in_progress", "live"}
            and is_top
            and (previous.period != period or not was_top)
        ):
            return PeriodStartEvent("inning_start", previous.last_ingested_at)
        return None

    if previous.status not in {"in_progress", "live"}:
        return None

    if profile.sport == "soccer":
        if not is_soccer_second_half(
            status=previous.status, period=previous.period, clock=previous.clock
        ) and is_soccer_second_half(
            status=payload.status, period=payload.period, clock=payload.clock
        ):
            return PeriodStartEvent("second_half_start", previous.last_ingested_at)
        if not is_soccer_extra_time(
            status=previous.status, period=previous.period
        ) and is_soccer_extra_time(status=payload.status, period=payload.period):
            return PeriodStartEvent("extra_time_start", previous.last_ingested_at)
        return None

    if profile.sport not in {"basketball", "football", "hockey"}:
        return None
    regulation = (
        3 if profile.sport == "hockey" else profile.basketball_regulation_periods or 4
    )
    period = payload.period or 0
    if (
        not 2 <= period <= regulation
        or previous.period not in {period - 1, period}
        or not _has_time_remaining(payload.clock)
    ):
        return None
    if previous.period == period:
        clock = (previous.clock or "").strip().upper()
        was_break = clock in {
            "HT",
            "HALFTIME",
            "0:00",
            "00:00",
            "0.0",
            "0:00.0",
        } or any(marker in clock for marker in ("END", "HALFTIME", "INTERMISSION"))
        if not was_break:
            return None
    if profile.sport == "hockey":
        alert_type = "period_start"
    elif regulation == 2:
        alert_type = "second_half_start"
    else:
        alert_type = "quarter_start"
    return PeriodStartEvent(alert_type, previous.last_ingested_at)
