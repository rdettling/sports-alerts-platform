from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Alert,
    AlertDelivery,
    Game,
    Team,
    User,
    UserAlertPreference,
    UserGameAlertOverride,
    UserGameFollow,
    UserGameUnfollow,
    UserTeamFollow,
)
from app.services.alert_delivery import deliver_email_alert_now, deliver_push_alert_now
from app.services.alert_preferences import AlertSettings, resolve_alert_settings
from app.services.leagues import get_alert_types, get_league_profile
from app.worker.soccer import SoccerDerivedEvents


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


def _parse_soccer_minute(clock: str | None) -> int | None:
    if not clock:
        return None
    text = clock.strip().replace("'", "")
    if not text:
        return None
    base_text = text.split("+", 1)[0].strip()
    try:
        return int(base_text)
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _load_game_watch_times(db: Session, games: list[Game]) -> dict[int, dict[int, datetime]]:
    game_ids = [game.id for game in games]
    if not game_ids:
        return {}
    game_map = {game.id: game for game in games}

    direct_rows = db.execute(
        select(UserGameFollow.game_id, UserGameFollow.user_id, UserGameFollow.created_at).where(UserGameFollow.game_id.in_(game_ids))
    ).all()
    by_game: dict[int, dict[int, datetime]] = {game_id: {} for game_id in game_ids}
    for game_id, user_id, created_at in direct_rows:
        existing = by_game.setdefault(game_id, {}).get(user_id)
        followed_at = _as_utc(created_at)
        if existing is None or followed_at < existing:
            by_game[game_id][user_id] = followed_at

    team_ids = sorted({team_id for game in games for team_id in (game.home_team_id, game.away_team_id)})
    if team_ids:
        team_rows = db.execute(
            select(UserTeamFollow.team_id, UserTeamFollow.user_id, UserTeamFollow.created_at).where(UserTeamFollow.team_id.in_(team_ids))
        ).all()
        watchers_by_team: dict[int, dict[int, datetime]] = {}
        for team_id, user_id, created_at in team_rows:
            followed_at = _as_utc(created_at)
            existing = watchers_by_team.setdefault(team_id, {}).get(user_id)
            if existing is None or followed_at < existing:
                watchers_by_team[team_id][user_id] = followed_at

        for game_id, game in game_map.items():
            for team_id in (game.home_team_id, game.away_team_id):
                for user_id, followed_at in watchers_by_team.get(team_id, {}).items():
                    existing = by_game.setdefault(game_id, {}).get(user_id)
                    if existing is None or followed_at < existing:
                        by_game[game_id][user_id] = followed_at

    unfollow_rows = db.execute(
        select(UserGameUnfollow.game_id, UserGameUnfollow.user_id).where(UserGameUnfollow.game_id.in_(game_ids))
    ).all()
    for game_id, user_id in unfollow_rows:
        if game_id in by_game:
            by_game[game_id].pop(user_id, None)
    return by_game


def _load_preferences_by_user_league(
    db: Session,
    user_ids: set[int],
    leagues: set[str],
) -> dict[tuple[int, str, str], UserAlertPreference]:
    if not user_ids or not leagues:
        return {}
    rows = db.scalars(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id.in_(sorted(user_ids)),
            UserAlertPreference.league.in_(sorted(leagues)),
        )
    ).all()
    return {(row.user_id, row.league, row.alert_type): row for row in rows}


def _load_overrides_by_user_game(db: Session, user_ids: set[int], game_ids: list[int]) -> dict[tuple[int, int, str], UserGameAlertOverride]:
    if not user_ids or not game_ids:
        return {}
    rows = db.scalars(
        select(UserGameAlertOverride).where(
            UserGameAlertOverride.user_id.in_(sorted(user_ids)),
            UserGameAlertOverride.game_id.in_(game_ids),
        )
    ).all()
    return {(row.user_id, row.game_id, row.alert_type): row for row in rows}


def _alert_settings_for(
    preferences_by_key: dict[tuple[int, str, str], UserAlertPreference],
    overrides_by_key: dict[tuple[int, int, str], UserGameAlertOverride],
    *,
    user_id: int,
    game: Game,
    alert_type: str,
) -> AlertSettings | None:
    if alert_type not in get_alert_types(game.league):
        return None
    return resolve_alert_settings(
        game.league,
        alert_type,
        preferences_by_key.get((user_id, game.league, alert_type)),
        overrides_by_key.get((user_id, game.id, alert_type)),
    )


def _should_trigger_close_game_late(game: Game, is_enabled: bool, margin_threshold: int | None, time_threshold: int | None) -> bool:
    if not is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.home_score is None or game.away_score is None:
        return False
    resolved_margin = margin_threshold or 5
    resolved_seconds = time_threshold or 120
    if abs(game.home_score - game.away_score) > resolved_margin:
        return False
    if (game.period or 0) < 4:
        return False
    seconds_left = _parse_clock_seconds(game.clock)
    return seconds_left is not None and seconds_left <= resolved_seconds


def _should_trigger_inning_start(game: Game, is_enabled: bool, inning_threshold: int | None) -> bool:
    if not is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.period is None:
        return False
    return game.period >= (inning_threshold or 7)


def _should_trigger_overtime_start(game: Game, is_enabled: bool) -> bool:
    return (
        is_enabled
        and get_league_profile(game.league).sport in {"basketball", "football"}
        and not game.is_final
        and game.status in {"in_progress", "live"}
        and (game.period or 0) >= 5
    )


def _should_trigger_extra_innings_start(game: Game, is_enabled: bool) -> bool:
    return (
        is_enabled
        and get_league_profile(game.league).sport == "baseball"
        and not game.is_final
        and game.status in {"in_progress", "live"}
        and (game.period or 0) >= 10
    )


def _should_trigger_penalty_kicks(game: Game, is_enabled: bool) -> bool:
    if not is_enabled:
        return False
    if get_league_profile(game.league).sport != "soccer":
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.home_score is None or game.away_score is None:
        return False
    if game.home_score != game.away_score:
        return False
    if (game.period or 0) >= 5:
        return True
    if game.period not in {3, 4}:
        return False
    minute = _parse_soccer_minute(game.clock)
    return minute is not None and minute >= 117


def _append_candidate_alert(
    candidate_alerts: list[Alert],
    candidate_event_keys: set[str],
    *,
    user_id: int,
    game_id: int,
    alert_type: str,
    event_key: str,
    event_data: dict[str, object],
) -> None:
    if event_key in candidate_event_keys:
        return
    candidate_event_keys.add(event_key)
    candidate_alerts.append(
        Alert(
            user_id=user_id,
            game_id=game_id,
            alert_type=alert_type,
            event_key=event_key,
            event_data=event_data,
        )
    )


def _followed_by_game_start(followed_at: datetime | None, game: Game) -> bool:
    return followed_at is not None and followed_at <= _as_utc(game.scheduled_start_time)


def evaluate_and_record_alerts(
    db: Session,
    games: list[Game],
    *,
    soccer_events: dict[int, SoccerDerivedEvents] | None = None,
) -> int:
    if not games:
        return 0
    soccer_events = soccer_events or {}
    watch_times_by_game = _load_game_watch_times(db, games)
    all_user_ids = {user_id for users in watch_times_by_game.values() for user_id in users}
    leagues = {game.league for game in games}
    preferences_by_key = _load_preferences_by_user_league(db, all_user_ids, leagues)
    overrides_by_key = _load_overrides_by_user_game(db, all_user_ids, [game.id for game in games])

    candidate_alerts: list[Alert] = []
    candidate_event_keys: set[str] = set()
    for game in games:
        user_watch_times = watch_times_by_game.get(game.id, {})
        for user_id, followed_at in user_watch_times.items():
            game_start = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="game_start"
            )
            if game_start and game_start.is_enabled and game.status in {"in_progress", "live"} and _followed_by_game_start(followed_at, game):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="game_start",
                    event_key=f"{user_id}:{game.id}:game_start",
                    event_data={"status": game.status},
                )

            final_result = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="final_result"
            )
            if final_result and final_result.is_enabled and (game.is_final or game.status == "final"):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="final_result",
                    event_key=f"{user_id}:{game.id}:final_result",
                    event_data={"status": game.status},
                )

            soccer_event = soccer_events.get(game.id)
            score_change_event = soccer_event.score_change if soccer_event is not None else None
            score_changed = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="score_changed"
            )
            if score_change_event and score_changed and score_changed.is_enabled:
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="score_changed",
                    event_key=f"{user_id}:{game.id}:score_changed:{score_change_event.new_away_score}-{score_change_event.new_home_score}",
                    event_data={
                        "status": score_change_event.status,
                        "period": score_change_event.period,
                        "clock": score_change_event.clock or "",
                        "previous_home_score": score_change_event.previous_home_score,
                        "previous_away_score": score_change_event.previous_away_score,
                        "new_home_score": score_change_event.new_home_score,
                        "new_away_score": score_change_event.new_away_score,
                        "scoring_side": score_change_event.scoring_side,
                        "is_inferred_goal": score_change_event.is_inferred_goal,
                    },
                )

            second_half = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="second_half_start"
            )
            if soccer_event and soccer_event.second_half_started and second_half and second_half.is_enabled:
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="second_half_start",
                    event_key=f"{user_id}:{game.id}:second_half_start",
                    event_data={"status": game.status, "period": game.period or 0, "clock": game.clock or ""},
                )

            extra_time = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="extra_time_start"
            )
            if soccer_event and soccer_event.extra_time_started and extra_time and extra_time.is_enabled:
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="extra_time_start",
                    event_key=f"{user_id}:{game.id}:extra_time_start",
                    event_data={"status": game.status, "period": game.period or 0, "clock": game.clock or ""},
                )

            penalty_kicks = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="penalty_kicks"
            )
            if penalty_kicks and _should_trigger_penalty_kicks(game, penalty_kicks.is_enabled):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="penalty_kicks",
                    event_key=f"{user_id}:{game.id}:penalty_kicks",
                    event_data={"status": game.status, "period": game.period or 0, "clock": game.clock or ""},
                )

            close_game = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="close_game_late"
            )
            if close_game and _should_trigger_close_game_late(
                game,
                close_game.is_enabled,
                close_game.close_game_margin_threshold,
                close_game.close_game_time_threshold_seconds,
            ):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="close_game_late",
                    event_key=f"{user_id}:{game.id}:close_game_late",
                    event_data={"period": game.period or 0, "clock": game.clock or "", "status": game.status},
                )

            overtime = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="overtime_start"
            )
            if overtime and _should_trigger_overtime_start(game, overtime.is_enabled):
                period = game.period or 0
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="overtime_start",
                    event_key=f"{user_id}:{game.id}:overtime_start:{period}",
                    event_data={"period": period, "clock": game.clock or "", "status": game.status},
                )

            extra_innings = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="extra_innings_start"
            )
            if extra_innings and _should_trigger_extra_innings_start(game, extra_innings.is_enabled):
                inning = game.period or 0
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="extra_innings_start",
                    event_key=f"{user_id}:{game.id}:extra_innings_start:{inning}",
                    event_data={"period": inning, "clock": game.clock or "", "status": game.status},
                )

            inning_start = _alert_settings_for(
                preferences_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="inning_start"
            )
            if inning_start and _should_trigger_inning_start(
                game,
                inning_start.is_enabled,
                inning_start.inning_start_threshold,
            ):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="inning_start",
                    event_key=f"{user_id}:{game.id}:inning_start",
                    event_data={"period": game.period or 0, "status": game.status},
                )

    if not candidate_alerts:
        return 0

    existing = {
        row[0]
        for row in db.execute(select(Alert.event_key).where(Alert.event_key.in_(sorted(candidate_event_keys)))).all()
    }
    to_insert = [alert for alert in candidate_alerts if alert.event_key not in existing]
    if not to_insert:
        return 0

    db.add_all(to_insert)
    db.flush()
    users_by_id = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(sorted({alert.user_id for alert in to_insert})))).all()
    }
    games_by_id = {game.id: game for game in games}
    teams_by_id = {
        team.id: team
        for team in db.scalars(
            select(Team).where(
                Team.id.in_(sorted({team_id for game in games_by_id.values() for team_id in (game.home_team_id, game.away_team_id)}))
            )
        ).all()
    }
    for alert in to_insert:
        game = games_by_id.get(alert.game_id)
        user = users_by_id.get(alert.user_id)
        mode = user.alert_delivery_mode if user else "email"
        if mode in {"email", "both"}:
            email_delivery = AlertDelivery(alert_id=alert.id, channel="email", status="pending")
            db.add(email_delivery)
            db.flush()
            deliver_email_alert_now(
                db,
                alert=alert,
                delivery=email_delivery,
                user=user,
                game=game,
                home=teams_by_id.get(game.home_team_id) if game else None,
                away=teams_by_id.get(game.away_team_id) if game else None,
                service="worker",
            )
        if mode in {"push", "both"}:
            push_delivery = AlertDelivery(alert_id=alert.id, channel="push", status="pending")
            db.add(push_delivery)
            db.flush()
            deliver_push_alert_now(
                db,
                alert=alert,
                delivery=push_delivery,
                user=user,
                game=game,
                home=teams_by_id.get(game.home_team_id) if game else None,
                away=teams_by_id.get(game.away_team_id) if game else None,
                service="worker",
            )
    return len(to_insert)
