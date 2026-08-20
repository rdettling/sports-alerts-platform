from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Alert,
    AlertDelivery,
    Game,
    PushSubscription,
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
from app.services.competitions import get_alert_types, get_competition_profile
from app.worker.alert_rules import detect_alerts
from app.worker.soccer import SoccerDerivedEvents


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


def _load_preferences_by_user_sport(
    db: Session,
    user_ids: set[int],
    sports: set[str],
) -> dict[tuple[int, str, str], UserAlertPreference]:
    if not user_ids or not sports:
        return {}
    rows = db.scalars(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id.in_(sorted(user_ids)),
            UserAlertPreference.sport.in_(sorted(sports)),
        )
    ).all()
    return {(row.user_id, row.sport, row.alert_type): row for row in rows}


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


def _resolve_settings_for_user_game(
    preferences_by_key: dict[tuple[int, str, str], UserAlertPreference],
    overrides_by_key: dict[tuple[int, int, str], UserGameAlertOverride],
    *,
    user_id: int,
    game: Game,
) -> dict[str, AlertSettings]:
    sport = get_competition_profile(game.competition).sport
    return {
        alert_type: resolve_alert_settings(
            sport,
            alert_type,
            preferences_by_key.get((user_id, sport, alert_type)),
            overrides_by_key.get((user_id, game.id, alert_type)),
        )
        for alert_type in get_alert_types(game.competition)
    }


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
    sports = {get_competition_profile(game.competition).sport for game in games}
    preferences_by_key = _load_preferences_by_user_sport(db, all_user_ids, sports)
    overrides_by_key = _load_overrides_by_user_game(db, all_user_ids, [game.id for game in games])

    candidate_alerts: list[Alert] = []
    candidate_event_keys: set[str] = set()
    for game in games:
        user_watch_times = watch_times_by_game.get(game.id, {})
        for user_id, followed_at in user_watch_times.items():
            settings_by_type = _resolve_settings_for_user_game(
                preferences_by_key,
                overrides_by_key,
                user_id=user_id,
                game=game,
            )
            for detected in detect_alerts(
                game,
                followed_at,
                settings_by_type,
                soccer_events.get(game.id),
            ):
                _append_candidate_alert(
                    candidate_alerts,
                    candidate_event_keys,
                    user_id=user_id,
                    game_id=game.id,
                    alert_type=detected.alert_type,
                    event_key=f"{user_id}:{game.id}:{detected.event_key_suffix}",
                    event_data=detected.event_data,
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
    push_user_ids = set(
        db.scalars(
            select(PushSubscription.user_id)
            .where(PushSubscription.user_id.in_(sorted(users_by_id)))
            .distinct()
        ).all()
    )
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
        if user and user.email_alerts_enabled:
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
        if user and user.id in push_user_ids:
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
