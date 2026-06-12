from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Game,
    GameOddsCurrent,
    SentAlert,
    Team,
    UserAlertDefault,
    UserGameAlertOverride,
    UserGameFollow,
    UserGameUnfollow,
    UserTeamFollow,
)
from app.services.alert_defaults import get_alert_default_values
from app.services.leagues import get_active_leagues, get_alert_types, league_supports_odds, list_supported_leagues
from worker.db import SessionLocal
from worker.config import settings
from worker.odds import MoneylineOdds, fetch_odds_index, game_key
from worker.planner import build_catalog_requests, build_fetch_plan, build_live_requests
from worker.providers.base import ProviderGame, SportsProvider

logger = logging.getLogger(__name__)
ODDS_MATCH_MAX_COMMENCE_DIFF = timedelta(hours=18)
SUPPORTED_LEAGUES = tuple(list_supported_leagues())


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


@dataclass(frozen=True)
class GameUpdateResult:
    did_update: bool
    game_id: int | None
    score_change_event: ScoreChangeEvent | None = None


def _normalize_league(league: str) -> str:
    value = league.strip().upper()
    if value not in SUPPORTED_LEAGUES:
        raise ValueError(f"Unsupported league: {league}")
    return value


def _assert_league_enabled(db: Session, league: str) -> None:
    if league not in set(get_active_leagues(db)):
        raise ValueError(f"League disabled: {league}")


def _catalog_interval_seconds(league: str) -> int:
    return max(1, settings.catalog_sync_interval_seconds)


def _live_interval_seconds(league: str) -> int:
    if league == "NBA":
        interval = settings.nba_live_sync_interval_seconds
    elif league == "MLB":
        interval = settings.mlb_live_sync_interval_seconds
    else:
        interval = settings.world_cup_live_sync_interval_seconds
    return max(1, interval)

def _next_scheduled_start(db: Session, league: str, now: datetime) -> datetime | None:
    return db.scalar(
        select(func.min(Game.scheduled_start_time)).where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now,
        )
    )


def _team_id_map(db: Session, league: str) -> dict[str, int]:
    rows = db.scalars(select(Team).where(Team.league == league)).all()
    return {team.external_team_id: team.id for team in rows}


def _team_name_map(db: Session, league: str) -> dict[int, str]:
    rows = db.scalars(select(Team).where(Team.league == league)).all()
    return {team.id: team.name for team in rows}


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


def _load_game_watchers(db: Session, games: list[Game]) -> dict[int, set[int]]:
    game_ids = [game.id for game in games]
    if not game_ids:
        return {}
    game_map = {game.id: game for game in games}

    direct_rows = db.execute(
        select(UserGameFollow.game_id, UserGameFollow.user_id).where(UserGameFollow.game_id.in_(game_ids))
    ).all()
    by_game: dict[int, set[int]] = {game_id: set() for game_id in game_ids}
    for game_id, user_id in direct_rows:
        by_game.setdefault(game_id, set()).add(user_id)

    team_ids = sorted(
        {
            team_id
            for game in games
            for team_id in (game.home_team_id, game.away_team_id)
        }
    )
    if team_ids:
        team_rows = db.execute(
            select(UserTeamFollow.team_id, UserTeamFollow.user_id).where(UserTeamFollow.team_id.in_(team_ids))
        ).all()
        watchers_by_team: dict[int, set[int]] = {}
        for team_id, user_id in team_rows:
            watchers_by_team.setdefault(team_id, set()).add(user_id)

        for game_id, game in game_map.items():
            by_game.setdefault(game_id, set()).update(watchers_by_team.get(game.home_team_id, set()))
            by_game.setdefault(game_id, set()).update(watchers_by_team.get(game.away_team_id, set()))

    unfollow_rows = db.execute(
        select(UserGameUnfollow.game_id, UserGameUnfollow.user_id).where(UserGameUnfollow.game_id.in_(game_ids))
    ).all()
    for game_id, user_id in unfollow_rows:
        if game_id in by_game:
            by_game[game_id].discard(user_id)
    return by_game


def _load_defaults_by_user_league(db: Session, user_ids: set[int], leagues: set[str]) -> dict[tuple[int, str, str], UserAlertDefault]:
    if not user_ids or not leagues:
        return {}
    rows = db.scalars(
        select(UserAlertDefault).where(
            UserAlertDefault.user_id.in_(sorted(user_ids)),
            UserAlertDefault.league.in_(sorted(leagues)),
        )
    ).all()
    return {(row.user_id, row.league, row.alert_type): row for row in rows}


def _ensure_alert_defaults_for_users(db: Session, user_ids: set[int], leagues: set[str]) -> None:
    if not user_ids or not leagues:
        return
    existing = {
        (row.user_id, row.league, row.alert_type)
        for row in db.scalars(
            select(UserAlertDefault).where(
                UserAlertDefault.user_id.in_(sorted(user_ids)),
                UserAlertDefault.league.in_(sorted(leagues)),
            )
        ).all()
    }
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


def _should_trigger_close_game_late(game: Game, is_enabled: bool, margin_threshold: int | None, time_threshold: int | None) -> bool:
    if not is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.home_score is None or game.away_score is None:
        return False
    resolved_margin = margin_threshold or 5
    resolved_seconds = time_threshold or 120
    margin = abs(game.home_score - game.away_score)
    if margin > resolved_margin:
        return False
    period = game.period or 0
    if period < 4:
        return False
    seconds_left = _parse_clock_seconds(game.clock)
    if seconds_left is None:
        return False
    return seconds_left <= resolved_seconds


def _should_trigger_inning_start(game: Game, is_enabled: bool, inning_threshold: int | None) -> bool:
    if not is_enabled:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.period is None:
        return False
    return game.period >= (inning_threshold or 7)


def _classify_world_cup_score_change(previous: Game | None, payload: ProviderGame, league: str) -> ScoreChangeEvent | None:
    if league != "WORLD_CUP" or previous is None:
        return None
    if payload.status not in {"in_progress", "live"}:
        return None
    if previous.home_score is None or previous.away_score is None:
        return None
    if payload.home_score is None or payload.away_score is None:
        return None

    home_delta = payload.home_score - previous.home_score
    away_delta = payload.away_score - previous.away_score
    if home_delta == 0 and away_delta == 0:
        return None
    if home_delta < 0 or away_delta < 0:
        return None
    if home_delta == 0 and away_delta == 1:
        scoring_side = "away"
        is_inferred_goal = True
    elif away_delta == 0 and home_delta == 1:
        scoring_side = "home"
        is_inferred_goal = True
    else:
        scoring_side = None
        is_inferred_goal = False

    return ScoreChangeEvent(
        previous_home_score=previous.home_score,
        previous_away_score=previous.away_score,
        new_home_score=payload.home_score,
        new_away_score=payload.away_score,
        scoring_side=scoring_side,
        is_inferred_goal=is_inferred_goal,
        period=payload.period,
        clock=payload.clock,
        status=payload.status,
    )


def _evaluate_and_record_alerts_batched(
    db: Session,
    games: list[Game],
    *,
    score_change_events: dict[int, ScoreChangeEvent] | None = None,
) -> int:
    if not games:
        return 0
    score_change_events = score_change_events or {}
    watchers_by_game = _load_game_watchers(db, games)
    all_user_ids = {user_id for users in watchers_by_game.values() for user_id in users}
    leagues = {game.league for game in games}
    _ensure_alert_defaults_for_users(db, all_user_ids, leagues)
    defaults_by_key = _load_defaults_by_user_league(db, all_user_ids, leagues)
    overrides_by_key = _load_overrides_by_user_game(db, all_user_ids, [game.id for game in games])

    candidate_alerts: list[SentAlert] = []
    candidate_dedupe_keys: set[str] = set()
    for game in games:
        user_ids = watchers_by_game.get(game.id, set())
        for user_id in user_ids:
            default_game_start = defaults_by_key.get((user_id, game.league, "game_start"))
            override_game_start = overrides_by_key.get((user_id, game.id, "game_start"))
            game_start_enabled, _, _, _ = _effective_alert_settings(default_game_start, override_game_start)
            if game_start_enabled and game.status in {"in_progress", "live"}:
                key = f"{user_id}:{game.id}:game_start"
                if key not in candidate_dedupe_keys:
                    candidate_dedupe_keys.add(key)
                    candidate_alerts.append(
                        SentAlert(
                            user_id=user_id,
                            game_id=game.id,
                            alert_type="game_start",
                            delivery_channel="email",
                            delivery_status="pending",
                            dedupe_key=key,
                            metadata_json={"status": game.status},
                        )
                    )

            default_final = defaults_by_key.get((user_id, game.league, "final_result"))
            override_final = overrides_by_key.get((user_id, game.id, "final_result"))
            final_enabled, _, _, _ = _effective_alert_settings(default_final, override_final)
            if final_enabled and (game.is_final or game.status == "final"):
                key = f"{user_id}:{game.id}:final_result"
                if key not in candidate_dedupe_keys:
                    candidate_dedupe_keys.add(key)
                    candidate_alerts.append(
                        SentAlert(
                            user_id=user_id,
                            game_id=game.id,
                            alert_type="final_result",
                            delivery_channel="email",
                            delivery_status="pending",
                            dedupe_key=key,
                            metadata_json={"status": game.status},
                        )
                    )

            score_change_event = score_change_events.get(game.id)
            default_score_changed = defaults_by_key.get((user_id, game.league, "score_changed"))
            override_score_changed = overrides_by_key.get((user_id, game.id, "score_changed"))
            score_changed_enabled, _, _, _ = _effective_alert_settings(default_score_changed, override_score_changed)
            if score_change_event and score_changed_enabled:
                key = f"{user_id}:{game.id}:score_changed:{score_change_event.new_away_score}-{score_change_event.new_home_score}"
                if key not in candidate_dedupe_keys:
                    candidate_dedupe_keys.add(key)
                    candidate_alerts.append(
                        SentAlert(
                            user_id=user_id,
                            game_id=game.id,
                            alert_type="score_changed",
                            delivery_channel="email",
                            delivery_status="pending",
                            dedupe_key=key,
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
                    )

            default_close = defaults_by_key.get((user_id, game.league, "close_game_late"))
            override_close = overrides_by_key.get((user_id, game.id, "close_game_late"))
            close_enabled, close_margin, close_seconds, _ = _effective_alert_settings(default_close, override_close)
            if _should_trigger_close_game_late(game, close_enabled, close_margin, close_seconds):
                key = f"{user_id}:{game.id}:close_game_late"
                if key not in candidate_dedupe_keys:
                    candidate_dedupe_keys.add(key)
                    candidate_alerts.append(
                        SentAlert(
                            user_id=user_id,
                            game_id=game.id,
                            alert_type="close_game_late",
                            delivery_channel="email",
                            delivery_status="pending",
                            dedupe_key=key,
                            metadata_json={"period": game.period or 0, "clock": game.clock or "", "status": game.status},
                        )
                    )

            default_inning = defaults_by_key.get((user_id, game.league, "inning_start"))
            override_inning = overrides_by_key.get((user_id, game.id, "inning_start"))
            inning_enabled, _, _, inning_threshold = _effective_alert_settings(default_inning, override_inning)
            if _should_trigger_inning_start(game, inning_enabled, inning_threshold):
                key = f"{user_id}:{game.id}:inning_start"
                if key not in candidate_dedupe_keys:
                    candidate_dedupe_keys.add(key)
                    candidate_alerts.append(
                        SentAlert(
                            user_id=user_id,
                            game_id=game.id,
                            alert_type="inning_start",
                            delivery_channel="email",
                            delivery_status="pending",
                            dedupe_key=key,
                            metadata_json={"period": game.period or 0, "status": game.status},
                        )
                    )

    if not candidate_alerts:
        return 0

    existing = {
        row[0]
        for row in db.execute(select(SentAlert.dedupe_key).where(SentAlert.dedupe_key.in_(sorted(candidate_dedupe_keys)))).all()
    }
    to_insert = [alert for alert in candidate_alerts if alert.dedupe_key not in existing]
    if to_insert:
        db.add_all(to_insert)
        db.flush()
    return len(to_insert)


def _upsert_game(db: Session, league: str, payload: ProviderGame, team_map: dict[str, int]) -> GameUpdateResult:
    home_id = team_map.get(payload.home_external_team_id)
    away_id = team_map.get(payload.away_external_team_id)
    if not home_id or not away_id:
        logger.warning(
            "Skipping game due to missing teams league=%s external_game_id=%s home_external_team_id=%s away_external_team_id=%s",
            league,
            payload.external_game_id,
            payload.home_external_team_id,
            payload.away_external_team_id,
        )
        return GameUpdateResult(did_update=False, game_id=None)

    existing = db.scalar(select(Game).where(Game.external_game_id == payload.external_game_id, Game.league == league))
    if existing:
        score_change_event = _classify_world_cup_score_change(existing, payload, league)
        before = (
            existing.context_label,
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        existing.context_label = payload.context_label
        existing.status = payload.status
        existing.home_score = payload.home_score
        existing.away_score = payload.away_score
        existing.period = payload.period
        existing.clock = payload.clock
        existing.is_final = payload.is_final
        existing.last_ingested_at = datetime.now(timezone.utc)
        after = (
            existing.context_label,
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        return GameUpdateResult(did_update=before != after, game_id=existing.id, score_change_event=score_change_event)

    created = Game(
        external_game_id=payload.external_game_id,
        league=league,
        home_team_id=home_id,
        away_team_id=away_id,
        scheduled_start_time=payload.scheduled_start_time,
        context_label=payload.context_label,
        status=payload.status,
        home_score=payload.home_score,
        away_score=payload.away_score,
        period=payload.period,
        clock=payload.clock,
        is_final=payload.is_final,
        last_ingested_at=datetime.now(timezone.utc),
    )
    db.add(created)
    db.flush()
    return GameUpdateResult(did_update=True, game_id=created.id)


def _upsert_game_odds(db: Session, game_id: int, odds: MoneylineOdds) -> bool:
    row = db.scalar(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id == game_id,
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == settings.odds_api_market,
        )
    )
    if row:
        before = (row.home_moneyline, row.away_moneyline, row.bookmaker)
        after = (odds.home_moneyline, odds.away_moneyline, odds.bookmaker)
        if before == after:
            return False
        row.home_moneyline = odds.home_moneyline
        row.away_moneyline = odds.away_moneyline
        row.bookmaker = odds.bookmaker
        row.fetched_at = odds.last_update or datetime.now(timezone.utc)
        return True

    db.add(
        GameOddsCurrent(
            game_id=game_id,
            provider=settings.odds_provider,
            market=settings.odds_api_market,
            home_moneyline=odds.home_moneyline,
            away_moneyline=odds.away_moneyline,
            bookmaker=odds.bookmaker,
            fetched_at=odds.last_update or datetime.now(timezone.utc),
        )
    )
    return True


def _delete_game_odds(db: Session, game_id: int) -> bool:
    row = db.scalar(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id == game_id,
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == settings.odds_api_market,
        )
    )
    if not row:
        return False
    db.delete(row)
    return True


def _select_best_odds_for_game(
    options: list[MoneylineOdds] | MoneylineOdds | None,
    scheduled_start_time: datetime,
) -> MoneylineOdds | None:
    if options is None:
        return None
    candidates = options if isinstance(options, list) else [options]
    if not candidates:
        return None

    target = scheduled_start_time if scheduled_start_time.tzinfo else scheduled_start_time.replace(tzinfo=timezone.utc)
    with_commence = [odds for odds in candidates if odds.commence_time]
    if not with_commence:
        return candidates[0]

    closest = min(
        with_commence,
        key=lambda odds: abs(((odds.commence_time if odds.commence_time.tzinfo else odds.commence_time.replace(tzinfo=timezone.utc)) - target).total_seconds()),
    )
    closest_commence = closest.commence_time if closest.commence_time.tzinfo else closest.commence_time.replace(tzinfo=timezone.utc)
    if abs((closest_commence - target).total_seconds()) > ODDS_MATCH_MAX_COMMENCE_DIFF.total_seconds():
        return None
    return closest


def _serialize_games(games: list[ProviderGame]) -> str:
    payload = [
        {
            "id": game.external_game_id,
            "status": game.status,
            "home": game.home_score,
            "away": game.away_score,
            "period": game.period,
            "clock": game.clock,
            "final": game.is_final,
            "start": game.scheduled_start_time.isoformat(),
        }
        for game in sorted(games, key=lambda item: item.external_game_id)
    ]
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _upsert_games_and_collect(
    db: Session,
    league: str,
    provider_games: list[ProviderGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
    *,
    only_external_ids: set[str] | None = None,
) -> tuple[int, list[int], dict[int, tuple[str, str]], dict[int, ScoreChangeEvent]]:
    updated = 0
    touched_game_ids: list[int] = []
    game_key_by_id: dict[int, tuple[str, str]] = {}
    score_change_events: dict[int, ScoreChangeEvent] = {}
    for provider_game in provider_games:
        if only_external_ids is not None and provider_game.external_game_id not in only_external_ids:
            continue
        result = _upsert_game(db, league, provider_game, team_map)
        if result.did_update:
            updated += 1
        if result.game_id:
            touched_game_ids.append(result.game_id)
            home_id = team_map.get(provider_game.home_external_team_id)
            away_id = team_map.get(provider_game.away_external_team_id)
            home_name = team_names.get(home_id) if home_id else None
            away_name = team_names.get(away_id) if away_id else None
            if home_name and away_name:
                game_key_by_id[result.game_id] = game_key(home_name, away_name)
            if result.score_change_event is not None:
                score_change_events[result.game_id] = result.score_change_event
    return updated, touched_game_ids, game_key_by_id, score_change_events


def _games_missing_pregame_snapshot(db: Session, league: str, now: datetime) -> list[Game]:
    pregame_cutoff = now + timedelta(hours=max(1, settings.odds_pregame_window_hours))
    rows = db.scalars(
        select(Game)
        .where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now,
            Game.scheduled_start_time <= pregame_cutoff,
        )
        .order_by(Game.scheduled_start_time.asc())
    ).all()
    if not rows:
        return []
    game_ids = [game.id for game in rows]
    existing_ids = {
        game_id
        for game_id, in db.execute(
            select(GameOddsCurrent.game_id).where(
                GameOddsCurrent.game_id.in_(game_ids),
                GameOddsCurrent.provider == settings.odds_provider,
                GameOddsCurrent.market == settings.odds_api_market,
            )
        ).all()
    }
    return [game for game in rows if game.id not in existing_ids]


def run_catalog_sync(provider: SportsProvider, league: str = "NBA") -> dict[str, int | str]:
    league = _normalize_league(league)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _assert_league_enabled(db, league)
        requests = build_catalog_requests(db, league, now=now)
        team_map = _team_id_map(db, league)
        team_names = _team_name_map(db, league)
        all_games = provider.fetch_games(league, requests)
        updated, touched_game_ids, game_key_by_id, score_change_events = _upsert_games_and_collect(db, league, all_games, team_map, team_names)

        odds_candidates = _games_missing_pregame_snapshot(db, league, now) if settings.odds_enabled and league_supports_odds(league) else []
        odds_calls = 0
        odds_snapshots_created = 0
        if odds_candidates:
            odds_by_matchup = fetch_odds_index(league)
            odds_calls = 1
            for game in odds_candidates:
                key = game_key_by_id.get(game.id)
                if key is None:
                    home_name = team_names.get(game.home_team_id)
                    away_name = team_names.get(game.away_team_id)
                    if not home_name or not away_name:
                        continue
                    key = game_key(home_name, away_name)
                matchup_odds = odds_by_matchup.get(key)
                odds = _select_best_odds_for_game(matchup_odds, game.scheduled_start_time)
                if odds and _upsert_game_odds(db, game.id, odds):
                    odds_snapshots_created += 1

        db.flush()
        touched_games = [game for game in (db.get(Game, game_id) for game_id in touched_game_ids) if game is not None]
        alerts_created = _evaluate_and_record_alerts_batched(db, touched_games, score_change_events=score_change_events)
        db.commit()

        logger.info(
            "Catalog sync league=%s checked=%s updated=%s odds_candidates=%s odds_snapshots_created=%s odds_calls=%s alerts_created=%s",
            league,
            len(all_games),
            updated,
            len(odds_candidates),
            odds_snapshots_created,
            odds_calls,
            alerts_created,
        )
        return {
            "status": "success",
            "job_type": "catalog_sync",
            "league": league,
            "games_checked": len(all_games),
            "games_updated": updated,
            "odds_candidates": len(odds_candidates),
            "odds_snapshots_created": odds_snapshots_created,
            "next_poll_seconds": _catalog_interval_seconds(league),
        }
    except Exception:
        db.rollback()
        logger.exception("Catalog sync failed")
        return {
            "status": "failed",
            "job_type": "catalog_sync",
            "league": league,
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": _catalog_interval_seconds(league),
        }
    finally:
        db.close()


def run_live_sync(provider: SportsProvider, league: str = "NBA") -> dict[str, int | str]:
    league = _normalize_league(league)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _assert_league_enabled(db, league)
        requests = build_live_requests(db, league)
        if not requests:
            next_scheduled = _next_scheduled_start(db, league, now)
            if next_scheduled is None:
                mode = "no_upcoming"
                next_scheduled_iso: str | None = None
            else:
                mode = "waiting_for_start"
                next_scheduled_iso = (next_scheduled if next_scheduled.tzinfo else next_scheduled.replace(tzinfo=timezone.utc)).isoformat()
            return {
                "status": "success",
                "job_type": "live_sync",
                "league": league,
                "has_live_games": "false",
                "next_scheduled_start_at": next_scheduled_iso,
                "games_checked": 0,
                "games_updated": 0,
                "next_poll_seconds": _catalog_interval_seconds(league),
                "mode": mode,
            }

        team_map = _team_id_map(db, league)
        team_names = _team_name_map(db, league)
        provider_games = provider.fetch_games(league, requests)
        candidate_ids = {
            external_id
            for external_id, in db.execute(
                select(Game.external_game_id).where(
                    Game.league == league,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live", "scheduled")),
                )
            ).all()
        }
        updated, touched_game_ids, _, score_change_events = _upsert_games_and_collect(
            db,
            league,
            provider_games,
            team_map,
            team_names,
            only_external_ids=candidate_ids,
        )
        db.flush()
        touched_games = [game for game in (db.get(Game, game_id) for game_id in touched_game_ids) if game is not None]
        alerts_created = _evaluate_and_record_alerts_batched(db, touched_games, score_change_events=score_change_events)
        has_live_games = bool(
            db.scalar(
                select(func.count(Game.id)).where(
                    Game.league == league,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live")),
                )
            )
            or 0
        )
        next_scheduled = _next_scheduled_start(db, league, now)
        db.commit()
        logger.info(
            "Live sync league=%s checked=%s updated=%s alerts_created=%s has_live_games=%s",
            league,
            len(provider_games),
            updated,
            alerts_created,
            has_live_games,
        )
        return {
            "status": "success",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "true" if has_live_games else "false",
            "next_scheduled_start_at": (
                (next_scheduled if next_scheduled.tzinfo else next_scheduled.replace(tzinfo=timezone.utc)).isoformat()
                if next_scheduled is not None
                else None
            ),
            "games_checked": len(provider_games),
            "games_updated": updated,
            "next_poll_seconds": _live_interval_seconds(league) if has_live_games else _catalog_interval_seconds(league),
            "mode": "live" if has_live_games else ("waiting_for_start" if next_scheduled is not None else "no_upcoming"),
        }
    except Exception:
        db.rollback()
        logger.exception("Live sync failed")
        return {
            "status": "failed",
            "job_type": "live_sync",
            "league": league,
            "has_live_games": "false",
            "next_scheduled_start_at": None,
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": _live_interval_seconds(league),
            "mode": "live",
        }
    finally:
        db.close()


def run_ingest_cycle(provider: SportsProvider) -> dict[str, int | str]:
    # Legacy compatibility path used by existing tests and tooling.
    return run_catalog_sync(provider, league="NBA")
