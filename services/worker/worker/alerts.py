from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Game,
    SentAlert,
    Team,
    User,
    UserAlertDefault,
    UserGameAlertOverride,
    UserGameFollow,
    UserGameUnfollow,
    UserTeamFollow,
)
from app.services.alert_defaults import get_alert_default_values
from app.services.alert_delivery import deliver_alert_now
from app.services.leagues import get_alert_types


@dataclass(frozen=True)
class ScoreChangeEvent:
    previous_home_score: int
    previous_away_score: int
    new_home_score: int
    new_away_score: int
    scoring_side: str | None
    is_inferred_goal: bool
    period: int | None
    clock: str | None
    status: str


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


def _load_user_alert_defaults(db: Session, user_ids: set[int], leagues: set[str]) -> list[UserAlertDefault]:
    if not user_ids or not leagues:
        return []
    return db.scalars(
        select(UserAlertDefault).where(
            UserAlertDefault.user_id.in_(sorted(user_ids)),
            UserAlertDefault.league.in_(sorted(leagues)),
        )
    ).all()


def _load_defaults_by_user_league(db: Session, user_ids: set[int], leagues: set[str]) -> dict[tuple[int, str, str], UserAlertDefault]:
    rows = _load_user_alert_defaults(db, user_ids, leagues)
    return {(row.user_id, row.league, row.alert_type): row for row in rows}


def _ensure_alert_defaults_for_users(db: Session, user_ids: set[int], leagues: set[str]) -> None:
    if not user_ids or not leagues:
        return
    existing = {(row.user_id, row.league, row.alert_type) for row in _load_user_alert_defaults(db, user_ids, leagues)}
    now = datetime.now(timezone.utc)
    created = False
    for user_id in sorted(user_ids):
        for league in sorted(leagues):
            for alert_type in get_alert_types(league):
                key = (user_id, league, alert_type)
                if key in existing:
                    continue
                defaults = get_alert_default_values(alert_type)
                db.add(
                    UserAlertDefault(
                        user_id=user_id,
                        league=league,
                        alert_type=alert_type,
                        is_enabled=defaults.is_enabled,
                        close_game_margin_threshold=defaults.close_game_margin_threshold,
                        close_game_time_threshold_seconds=defaults.close_game_time_threshold_seconds,
                        inning_start_threshold=defaults.inning_start_threshold,
                        created_at=now,
                        updated_at=now,
                    )
                )
                created = True
    if created:
        db.flush()


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


def _effective_alert_settings(
    default_pref: UserAlertDefault | None,
    override: UserGameAlertOverride | None,
) -> tuple[bool, int | None, int | None, int | None]:
    enabled = default_pref.is_enabled if default_pref else False
    margin = default_pref.close_game_margin_threshold if default_pref else None
    seconds = default_pref.close_game_time_threshold_seconds if default_pref else None
    inning = default_pref.inning_start_threshold if default_pref else None
    if override is not None:
        if override.is_enabled_override is not None:
            enabled = override.is_enabled_override
        if override.close_game_margin_threshold_override is not None:
            margin = override.close_game_margin_threshold_override
        if override.close_game_time_threshold_seconds_override is not None:
            seconds = override.close_game_time_threshold_seconds_override
        if override.inning_start_threshold_override is not None:
            inning = override.inning_start_threshold_override
    return enabled, margin, seconds, inning


def _alert_settings_for(
    defaults_by_key: dict[tuple[int, str, str], UserAlertDefault],
    overrides_by_key: dict[tuple[int, int, str], UserGameAlertOverride],
    *,
    user_id: int,
    game: Game,
    alert_type: str,
) -> tuple[bool, int | None, int | None, int | None]:
    return _effective_alert_settings(
        defaults_by_key.get((user_id, game.league, alert_type)),
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


def _append_candidate_alert(
    candidate_alerts: list[SentAlert],
    candidate_dedupe_keys: set[str],
    *,
    user_id: int,
    game_id: int,
    alert_type: str,
    dedupe_key: str,
    metadata_json: dict[str, object],
) -> None:
    if dedupe_key in candidate_dedupe_keys:
        return
    candidate_dedupe_keys.add(dedupe_key)
    candidate_alerts.append(
        SentAlert(
            user_id=user_id,
            game_id=game_id,
            alert_type=alert_type,
            delivery_channel="email",
            delivery_status="sent",
            dedupe_key=dedupe_key,
            metadata_json=metadata_json,
        )
    )


def _followed_by_game_start(followed_at: datetime | None, game: Game) -> bool:
    return followed_at is not None and followed_at <= _as_utc(game.scheduled_start_time)


def evaluate_and_record_alerts(
    db: Session,
    games: list[Game],
    *,
    score_change_events: dict[int, ScoreChangeEvent] | None = None,
) -> int:
    if not games:
        return 0
    score_change_events = score_change_events or {}
    watch_times_by_game = _load_game_watch_times(db, games)
    all_user_ids = {user_id for users in watch_times_by_game.values() for user_id in users}
    leagues = {game.league for game in games}
    _ensure_alert_defaults_for_users(db, all_user_ids, leagues)
    defaults_by_key = _load_defaults_by_user_league(db, all_user_ids, leagues)
    overrides_by_key = _load_overrides_by_user_game(db, all_user_ids, [game.id for game in games])

    candidate_alerts: list[SentAlert] = []
    candidate_dedupe_keys: set[str] = set()
    for game in games:
        user_watch_times = watch_times_by_game.get(game.id, {})
        for user_id, followed_at in user_watch_times.items():
            game_start_enabled, _, _, _ = _alert_settings_for(
                defaults_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="game_start"
            )
            if game_start_enabled and game.status in {"in_progress", "live"} and _followed_by_game_start(followed_at, game):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_dedupe_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="game_start",
                    dedupe_key=f"{user_id}:{game.id}:game_start",
                    metadata_json={"status": game.status},
                )

            final_enabled, _, _, _ = _alert_settings_for(
                defaults_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="final_result"
            )
            if final_enabled and (game.is_final or game.status == "final"):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_dedupe_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="final_result",
                    dedupe_key=f"{user_id}:{game.id}:final_result",
                    metadata_json={"status": game.status},
                )

            score_change_event = score_change_events.get(game.id)
            score_changed_enabled, _, _, _ = _alert_settings_for(
                defaults_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="score_changed"
            )
            if score_change_event and score_changed_enabled:
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_dedupe_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="score_changed",
                    dedupe_key=f"{user_id}:{game.id}:score_changed:{score_change_event.new_away_score}-{score_change_event.new_home_score}",
                    metadata_json={
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

            close_enabled, close_margin, close_seconds, _ = _alert_settings_for(
                defaults_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="close_game_late"
            )
            if _should_trigger_close_game_late(game, close_enabled, close_margin, close_seconds):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_dedupe_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="close_game_late",
                    dedupe_key=f"{user_id}:{game.id}:close_game_late",
                    metadata_json={"period": game.period or 0, "clock": game.clock or "", "status": game.status},
                )

            inning_enabled, _, _, inning_threshold = _alert_settings_for(
                defaults_by_key, overrides_by_key, user_id=user_id, game=game, alert_type="inning_start"
            )
            if _should_trigger_inning_start(game, inning_enabled, inning_threshold):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_dedupe_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type="inning_start",
                    dedupe_key=f"{user_id}:{game.id}:inning_start",
                    metadata_json={"period": game.period or 0, "status": game.status},
                )

    if not candidate_alerts:
        return 0

    existing = {
        row[0]
        for row in db.execute(select(SentAlert.dedupe_key).where(SentAlert.dedupe_key.in_(sorted(candidate_dedupe_keys)))).all()
    }
    to_insert = [alert for alert in candidate_alerts if alert.dedupe_key not in existing]
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
        deliver_alert_now(
            db,
            alert=alert,
            user=users_by_id.get(alert.user_id),
            game=game,
            home=teams_by_id.get(game.home_team_id) if game else None,
            away=teams_by_id.get(game.away_team_id) if game else None,
            service="worker",
        )
    return len(to_insert)
