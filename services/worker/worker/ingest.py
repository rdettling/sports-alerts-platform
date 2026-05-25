from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Game,
    GameOddsCurrent,
    SentAlert,
    Team,
    UserAlertPreference,
    UserGameFollow,
    UserTeamFollow,
)
from worker.db import SessionLocal
from worker.config import settings
from worker.odds import MoneylineOdds, fetch_nba_odds_index, game_key
from worker.planner import build_catalog_requests, build_fetch_plan, build_live_requests
from worker.providers.base import NbaProvider, ProviderGame

logger = logging.getLogger(__name__)
ODDS_MATCH_MAX_COMMENCE_DIFF = timedelta(hours=18)


def _team_id_map(db: Session) -> dict[str, int]:
    rows = db.scalars(select(Team)).all()
    return {team.external_team_id: team.id for team in rows}


def _team_name_map(db: Session) -> dict[int, str]:
    rows = db.scalars(select(Team)).all()
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
    return by_game


def _load_enabled_preferences(db: Session, user_ids: set[int]) -> dict[tuple[int, str], UserAlertPreference]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id.in_(sorted(user_ids)),
            UserAlertPreference.is_enabled.is_(True),
        )
    ).all()
    return {(row.user_id, row.alert_type): row for row in rows}


def _should_trigger_close_game_late(game: Game, preference: UserAlertPreference | None) -> bool:
    if not preference:
        return False
    if game.is_final or game.status not in {"in_progress", "live"}:
        return False
    if game.home_score is None or game.away_score is None:
        return False
    margin_threshold = preference.close_game_margin_threshold or 5
    time_threshold = preference.close_game_time_threshold_seconds or 120
    margin = abs(game.home_score - game.away_score)
    if margin > margin_threshold:
        return False
    period = game.period or 0
    if period < 4:
        return False
    seconds_left = _parse_clock_seconds(game.clock)
    if seconds_left is None:
        return False
    return seconds_left <= time_threshold


def _evaluate_and_record_alerts_batched(db: Session, games: list[Game]) -> int:
    if not games:
        return 0
    watchers_by_game = _load_game_watchers(db, games)
    all_user_ids = {user_id for users in watchers_by_game.values() for user_id in users}
    prefs_by_user_type = _load_enabled_preferences(db, all_user_ids)

    candidate_alerts: list[SentAlert] = []
    candidate_dedupe_keys: set[str] = set()
    for game in games:
        user_ids = watchers_by_game.get(game.id, set())
        for user_id in user_ids:
            if prefs_by_user_type.get((user_id, "game_start")) and game.status in {"in_progress", "live"}:
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

            if prefs_by_user_type.get((user_id, "final_result")) and (game.is_final or game.status == "final"):
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

            close_pref = prefs_by_user_type.get((user_id, "close_game_late"))
            if _should_trigger_close_game_late(game, close_pref):
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


def _upsert_game(db: Session, payload: ProviderGame, team_map: dict[str, int]) -> tuple[bool, int | None]:
    home_id = team_map.get(payload.home_external_team_id)
    away_id = team_map.get(payload.away_external_team_id)
    if not home_id or not away_id:
        logger.warning("Skipping game %s due to missing teams", payload.external_game_id)
        return False, None

    existing = db.scalar(select(Game).where(Game.external_game_id == payload.external_game_id, Game.league == "NBA"))
    if existing:
        before = (
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        existing.status = payload.status
        existing.home_score = payload.home_score
        existing.away_score = payload.away_score
        existing.period = payload.period
        existing.clock = payload.clock
        existing.is_final = payload.is_final
        existing.last_ingested_at = datetime.now(timezone.utc)
        after = (
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        return before != after, existing.id

    created = Game(
        external_game_id=payload.external_game_id,
        league="NBA",
        home_team_id=home_id,
        away_team_id=away_id,
        scheduled_start_time=payload.scheduled_start_time,
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
    return True, created.id


def _upsert_game_odds(db: Session, game_id: int, odds: MoneylineOdds) -> bool:
    row = db.scalar(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id == game_id,
            GameOddsCurrent.provider == "the_odds_api",
            GameOddsCurrent.market == "h2h",
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
            provider="the_odds_api",
            market="h2h",
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
            GameOddsCurrent.provider == "the_odds_api",
            GameOddsCurrent.market == "h2h",
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
    provider_games: list[ProviderGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
    *,
    only_external_ids: set[str] | None = None,
) -> tuple[int, list[int], dict[int, tuple[str, str]]]:
    updated = 0
    touched_game_ids: list[int] = []
    game_key_by_id: dict[int, tuple[str, str]] = {}
    for provider_game in provider_games:
        if only_external_ids is not None and provider_game.external_game_id not in only_external_ids:
            continue
        did_update, game_id = _upsert_game(db, provider_game, team_map)
        if did_update:
            updated += 1
        if game_id:
            touched_game_ids.append(game_id)
            home_id = team_map.get(provider_game.home_external_team_id)
            away_id = team_map.get(provider_game.away_external_team_id)
            home_name = team_names.get(home_id) if home_id else None
            away_name = team_names.get(away_id) if away_id else None
            if home_name and away_name:
                game_key_by_id[game_id] = game_key(home_name, away_name)
    return updated, touched_game_ids, game_key_by_id


def _games_missing_pregame_snapshot(db: Session, now: datetime) -> list[Game]:
    pregame_cutoff = now + timedelta(hours=max(1, settings.odds_pregame_window_hours))
    rows = db.scalars(
        select(Game)
        .where(
            Game.league == "NBA",
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


def run_catalog_sync(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        requests = build_catalog_requests(db, now=now)
        team_map = _team_id_map(db)
        team_names = _team_name_map(db)
        all_games = provider.fetch_games(requests)
        updated, touched_game_ids, game_key_by_id = _upsert_games_and_collect(db, all_games, team_map, team_names)

        odds_candidates = _games_missing_pregame_snapshot(db, now) if settings.odds_enabled else []
        odds_calls = 0
        odds_snapshots_created = 0
        if odds_candidates:
            odds_by_matchup = fetch_nba_odds_index()
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
        alerts_created = _evaluate_and_record_alerts_batched(db, touched_games)
        db.commit()

        logger.info(
            "Catalog sync checked=%s updated=%s odds_candidates=%s odds_snapshots_created=%s odds_calls=%s alerts_created=%s",
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
            "games_checked": len(all_games),
            "games_updated": updated,
            "odds_candidates": len(odds_candidates),
            "odds_snapshots_created": odds_snapshots_created,
            "next_poll_seconds": max(1, settings.catalog_sync_interval_seconds),
        }
    except Exception:
        db.rollback()
        logger.exception("Catalog sync failed")
        return {
            "status": "failed",
            "job_type": "catalog_sync",
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": max(1, settings.catalog_sync_interval_seconds),
        }
    finally:
        db.close()


def run_live_sync(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    try:
        live_game_ids = {
            external_id
            for external_id, in db.execute(
                select(Game.external_game_id).where(
                    Game.league == "NBA",
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live")),
                )
            ).all()
        }
        if not live_game_ids:
            return {
                "status": "success",
                "job_type": "live_sync",
                "games_checked": 0,
                "games_updated": 0,
                "next_poll_seconds": max(1, settings.live_sync_interval_seconds),
                "mode": "idle",
            }

        requests = build_live_requests(db)
        if not requests:
            return {
                "status": "success",
                "job_type": "live_sync",
                "games_checked": 0,
                "games_updated": 0,
                "next_poll_seconds": max(1, settings.live_sync_interval_seconds),
                "mode": "idle",
            }

        team_map = _team_id_map(db)
        team_names = _team_name_map(db)
        provider_games = provider.fetch_games(requests)
        updated, touched_game_ids, _ = _upsert_games_and_collect(
            db,
            provider_games,
            team_map,
            team_names,
            only_external_ids=live_game_ids,
        )
        db.flush()
        touched_games = [game for game in (db.get(Game, game_id) for game_id in touched_game_ids) if game is not None]
        alerts_created = _evaluate_and_record_alerts_batched(db, touched_games)
        db.commit()
        logger.info(
            "Live sync checked=%s updated=%s alerts_created=%s",
            len(provider_games),
            updated,
            alerts_created,
        )
        return {
            "status": "success",
            "job_type": "live_sync",
            "games_checked": len(provider_games),
            "games_updated": updated,
            "next_poll_seconds": max(1, settings.live_sync_interval_seconds),
            "mode": "live",
        }
    except Exception:
        db.rollback()
        logger.exception("Live sync failed")
        return {
            "status": "failed",
            "job_type": "live_sync",
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": max(1, settings.live_sync_interval_seconds),
            "mode": "live",
        }
    finally:
        db.close()


def run_ingest_cycle(provider: NbaProvider) -> dict[str, int | str]:
    # Legacy compatibility path used by existing tests and tooling.
    return run_catalog_sync(provider)
