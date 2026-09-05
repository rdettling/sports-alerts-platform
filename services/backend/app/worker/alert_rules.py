from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.models import Game
from app.services.alert_preferences import AlertSettings
from app.services.competitions import get_competition_profile
from app.worker.score_events import ScoreChangeEvent
from app.worker.soccer import SoccerDerivedEvents, is_penalty_kicks_window


@dataclass(frozen=True)
class DetectedAlert:
    alert_type: str
    event_key_suffix: str
    event_data: dict[str, object]


def _event_snapshot(game: Game) -> dict[str, object]:
    return {
        "status": game.status,
        "period": game.period or 0,
        "clock": game.clock or "",
        "home_score": game.home_score,
        "away_score": game.away_score,
    }


def _parse_clock_seconds(clock: str | None) -> int | None:
    if not clock:
        return None
    text = clock.strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except ValueError:
        return None


def _followed_by_game_start(followed_at: datetime | None, game: Game) -> bool:
    if followed_at is None:
        return False
    scheduled_start = game.scheduled_start_time
    if scheduled_start.tzinfo is None:
        scheduled_start = scheduled_start.replace(tzinfo=timezone.utc)
    return followed_at <= scheduled_start


def _should_trigger_close_game_late(game: Game, settings: AlertSettings) -> bool:
    if not settings.is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.home_score is None or game.away_score is None:
        return False
    resolved_margin = settings.close_game_margin_threshold or 5
    resolved_seconds = settings.close_game_time_threshold_seconds or 120
    if abs(game.home_score - game.away_score) > resolved_margin:
        return False
    if (game.period or 0) < 4:
        return False
    seconds_left = _parse_clock_seconds(game.clock)
    return seconds_left is not None and seconds_left <= resolved_seconds


def _should_trigger_inning_start(game: Game, settings: AlertSettings) -> bool:
    if not settings.is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.period is None:
        return False
    return game.period >= (settings.inning_start_threshold or 7)


def _should_trigger_overtime_start(game: Game, settings: AlertSettings) -> bool:
    return (
        settings.is_enabled
        and get_competition_profile(game.competition).sport in {"basketball", "football"}
        and not game.is_final
        and game.status in {"in_progress", "live"}
        and (game.period or 0) >= 5
    )


def _should_trigger_extra_innings_start(game: Game, settings: AlertSettings) -> bool:
    return (
        settings.is_enabled
        and get_competition_profile(game.competition).sport == "baseball"
        and not game.is_final
        and game.status in {"in_progress", "live"}
        and (game.period or 0) >= 10
    )


def detect_alerts(
    game: Game,
    followed_at: datetime | None,
    settings_by_type: dict[str, AlertSettings],
    score_change: ScoreChangeEvent | None = None,
    soccer_events: SoccerDerivedEvents | None = None,
    *,
    close_game_already_notified: bool = False,
) -> list[DetectedAlert]:
    detected: list[DetectedAlert] = []

    game_start = settings_by_type.get("game_start")
    if (
        game_start
        and game_start.is_enabled
        and game.status in {"in_progress", "live"}
        and _followed_by_game_start(followed_at, game)
    ):
        detected.append(DetectedAlert("game_start", "game_start", _event_snapshot(game)))

    final_result = settings_by_type.get("final_result")
    if final_result and final_result.is_enabled and (game.is_final or game.status == "final"):
        detected.append(DetectedAlert("final_result", "final_result", _event_snapshot(game)))

    score_changed = settings_by_type.get("score_changed")
    lead_change = settings_by_type.get("lead_change")
    close_game = settings_by_type.get("close_game_late")
    fresh_close_game = bool(
        close_game
        and not close_game_already_notified
        and _should_trigger_close_game_late(game, close_game)
    )
    score_event_data = (
        {
            **_event_snapshot(game),
            "status": score_change.status,
            "period": score_change.period or 0,
            "clock": score_change.clock or "",
            "home_score": score_change.new_home_score,
            "away_score": score_change.new_away_score,
            "previous_home_score": score_change.previous_home_score,
            "previous_away_score": score_change.previous_away_score,
            "new_home_score": score_change.new_home_score,
            "new_away_score": score_change.new_away_score,
            "scoring_side": score_change.scoring_side,
            "is_inferred_goal": score_change.is_inferred_goal,
            "previous_leader": score_change.previous_leader,
            "new_leader": score_change.new_leader,
        }
        if score_change is not None
        else None
    )
    is_football_score_change = (
        score_change is not None
        and get_competition_profile(game.competition).sport == "football"
    )
    is_football_lead_change = (
        is_football_score_change
        and score_change.lead_changed
    )
    if is_football_lead_change and lead_change and lead_change.is_enabled:
        event_data = dict(score_event_data or {})
        if fresh_close_game:
            event_data["covers_close_game_late"] = True
        detected.append(
            DetectedAlert(
                "lead_change",
                f"lead_change:{score_change.new_away_score}-{score_change.new_home_score}",
                event_data,
            )
        )
    elif is_football_score_change and fresh_close_game:
        detected.append(
            DetectedAlert(
                "close_game_late",
                "close_game_late",
                score_event_data or {},
            )
        )
    elif score_change and score_changed and score_changed.is_enabled:
        detected.append(
            DetectedAlert(
                "score_changed",
                f"score_changed:{score_change.new_away_score}-{score_change.new_home_score}",
                score_event_data or {},
            )
        )

    second_half = settings_by_type.get("second_half_start")
    if soccer_events and soccer_events.second_half_started and second_half and second_half.is_enabled:
        detected.append(
            DetectedAlert(
                "second_half_start",
                "second_half_start",
                _event_snapshot(game),
            )
        )

    extra_time = settings_by_type.get("extra_time_start")
    if soccer_events and soccer_events.extra_time_started and extra_time and extra_time.is_enabled:
        detected.append(
            DetectedAlert(
                "extra_time_start",
                "extra_time_start",
                _event_snapshot(game),
            )
        )

    penalty_kicks = settings_by_type.get("penalty_kicks")
    if penalty_kicks and penalty_kicks.is_enabled and is_penalty_kicks_window(
        status=game.status,
        period=game.period,
        home_score=game.home_score,
        away_score=game.away_score,
        clock=game.clock,
    ):
        detected.append(
            DetectedAlert(
                "penalty_kicks",
                "penalty_kicks",
                _event_snapshot(game),
            )
        )

    if fresh_close_game and not is_football_score_change:
        detected.append(
            DetectedAlert(
                "close_game_late",
                "close_game_late",
                _event_snapshot(game),
            )
        )

    overtime = settings_by_type.get("overtime_start")
    if overtime and _should_trigger_overtime_start(game, overtime):
        period = game.period or 0
        detected.append(
            DetectedAlert(
                "overtime_start",
                f"overtime_start:{period}",
                _event_snapshot(game),
            )
        )

    extra_innings = settings_by_type.get("extra_innings_start")
    if extra_innings and _should_trigger_extra_innings_start(game, extra_innings):
        inning = game.period or 0
        detected.append(
            DetectedAlert(
                "extra_innings_start",
                f"extra_innings_start:{inning}",
                _event_snapshot(game),
            )
        )

    inning_start = settings_by_type.get("inning_start")
    if inning_start and _should_trigger_inning_start(game, inning_start):
        detected.append(
            DetectedAlert(
                "inning_start",
                "inning_start",
                _event_snapshot(game),
            )
        )

    return detected
