from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Game, Team
from app.db.session import SessionLocal
from app.services.leagues import get_active_leagues, get_league_profile, league_supports_odds, normalize_league
from app.worker import odds, soccer
from app.worker.alerts import evaluate_and_record_alerts
from app.worker.config import settings
from app.worker.planner import build_catalog_requests, build_live_requests
from app.worker.scoreboard import ScoreboardGame

logger = logging.getLogger(__name__)
LIVE_STATUS_RECHECK_GRACE = timedelta(hours=2)


class ScoreboardFetcher(Protocol):
    def fetch_games(self, league: str, dates: list[str]) -> list[ScoreboardGame]: ...


@dataclass(frozen=True)
class GameUpdateResult:
    did_update: bool
    game_id: int | None
    soccer_events: soccer.SoccerDerivedEvents | None = None


def _assert_league_enabled(db: Session, league: str) -> None:
    if league not in set(get_active_leagues(db)):
        raise ValueError(f"League disabled: {league}")


def _catalog_interval_seconds() -> int:
    return max(1, settings.catalog_sync_interval_seconds)


def _live_interval_seconds(league: str) -> int:
    return max(1, get_league_profile(league).live_sync_interval_seconds)


def _next_scheduled_start(db: Session, league: str, now: datetime) -> datetime | None:
    return db.scalar(
        select(func.min(Game.scheduled_start_time)).where(
            Game.league == league,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now - LIVE_STATUS_RECHECK_GRACE,
        )
    )


def _league_team_maps(db: Session, league: str) -> tuple[dict[str, int], dict[int, str]]:
    rows = db.scalars(select(Team).where(Team.league == league)).all()
    return (
        {team.external_team_id: team.id for team in rows},
        {team.id: team.name for team in rows},
    )


def _upsert_game(db: Session, league: str, payload: ScoreboardGame, team_map: dict[str, int]) -> GameUpdateResult:
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
        is_soccer = get_league_profile(league).sport == "soccer"
        previous_snapshot = soccer.snapshot_state(existing) if is_soccer else None
        soccer_events = soccer.classify_events(existing, payload) if is_soccer else None
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
        if previous_snapshot is not None and before != after:
            soccer.log_transition(previous_snapshot, payload, soccer_events)
        return GameUpdateResult(did_update=before != after, game_id=existing.id, soccer_events=soccer_events)

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


def _upsert_games_and_collect(
    db: Session,
    league: str,
    scoreboard_games: list[ScoreboardGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
    *,
    only_external_ids: set[str] | None = None,
) -> tuple[int, list[int], dict[int, tuple[str, str]], dict[int, soccer.SoccerDerivedEvents]]:
    updated = 0
    touched_game_ids: list[int] = []
    game_key_by_id: dict[int, tuple[str, str]] = {}
    soccer_events: dict[int, soccer.SoccerDerivedEvents] = {}
    for scoreboard_game in scoreboard_games:
        if only_external_ids is not None and scoreboard_game.external_game_id not in only_external_ids:
            continue
        result = _upsert_game(db, league, scoreboard_game, team_map)
        if result.did_update:
            updated += 1
        if result.game_id:
            touched_game_ids.append(result.game_id)
            home_id = team_map.get(scoreboard_game.home_external_team_id)
            away_id = team_map.get(scoreboard_game.away_external_team_id)
            home_name = team_names.get(home_id) if home_id else None
            away_name = team_names.get(away_id) if away_id else None
            if home_name and away_name:
                game_key_by_id[result.game_id] = odds.game_key(home_name, away_name)
            if result.soccer_events is not None:
                soccer_events[result.game_id] = result.soccer_events
    return updated, touched_game_ids, game_key_by_id, soccer_events


def _set_fetch_telemetry_context(provider: ScoreboardFetcher, db: Session | None) -> None:
    provider_context = getattr(provider, "set_telemetry_context", None)
    if callable(provider_context):
        provider_context(db)
    odds.set_telemetry_context(db)


def run_catalog_sync(provider: ScoreboardFetcher, league: str = "NBA") -> dict[str, int | str]:
    league = normalize_league(league)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _set_fetch_telemetry_context(provider, db)
        _assert_league_enabled(db, league)
        requests = build_catalog_requests(db, league, now=now)
        team_map, team_names = _league_team_maps(db, league)
        all_games = provider.fetch_games(league, requests)
        updated, touched_game_ids, game_key_by_id, soccer_events = _upsert_games_and_collect(db, league, all_games, team_map, team_names)
        if all_games and not touched_game_ids:
            raise RuntimeError(f"No {league} games could be mapped to catalog teams")

        odds_eligible_external_ids = None
        if league == "NFL":
            odds_eligible_external_ids = {
                game.external_game_id for game in all_games if game.season_slug != "preseason"
            }
        odds_candidates = (
            odds.games_missing_pregame_snapshot(
                db,
                league,
                now,
                eligible_external_ids=odds_eligible_external_ids,
            )
            if settings.odds_enabled and league_supports_odds(league)
            else []
        )
        odds_calls = 0
        odds_snapshots_created = 0
        if odds_candidates:
            odds_by_matchup = odds.fetch_odds_index(league)
            odds_calls = 1
            for game in odds_candidates:
                key = game_key_by_id.get(game.id)
                if key is None:
                    home_name = team_names.get(game.home_team_id)
                    away_name = team_names.get(game.away_team_id)
                    if not home_name or not away_name:
                        continue
                    key = odds.game_key(home_name, away_name)
                matchup_odds = odds_by_matchup.get(key)
                game_odds = odds.select_best_for_game(matchup_odds, game.scheduled_start_time)
                if game_odds and odds.upsert_game_odds(db, game.id, game_odds):
                    odds_snapshots_created += 1

        db.flush()
        touched_games = [game for game in (db.get(Game, game_id) for game_id in touched_game_ids) if game is not None]
        alerts_created = evaluate_and_record_alerts(db, touched_games, soccer_events=soccer_events)
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
            "alerts_created": alerts_created,
            "next_poll_seconds": _catalog_interval_seconds(),
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Catalog sync failed")
        return {
            "status": "failed",
            "job_type": "catalog_sync",
            "league": league,
            "error": str(exc),
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": _catalog_interval_seconds(),
        }
    finally:
        _set_fetch_telemetry_context(provider, None)
        db.close()


def run_live_sync(provider: ScoreboardFetcher, league: str = "NBA") -> dict[str, int | str]:
    league = normalize_league(league)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _set_fetch_telemetry_context(provider, db)
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
                "next_poll_seconds": _catalog_interval_seconds(),
                "mode": mode,
            }

        team_map, team_names = _league_team_maps(db, league)
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
        updated, touched_game_ids, _, soccer_events = _upsert_games_and_collect(
            db,
            league,
            provider_games,
            team_map,
            team_names,
            only_external_ids=candidate_ids,
        )
        db.flush()
        touched_games = [game for game in (db.get(Game, game_id) for game_id in touched_game_ids) if game is not None]
        alerts_created = evaluate_and_record_alerts(db, touched_games, soccer_events=soccer_events)
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
            "alerts_created": alerts_created,
            "next_poll_seconds": _live_interval_seconds(league) if has_live_games else _catalog_interval_seconds(),
            "mode": "live" if has_live_games else ("waiting_for_start" if next_scheduled is not None else "no_upcoming"),
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Live sync failed")
        return {
            "status": "failed",
            "job_type": "live_sync",
            "league": league,
            "error": str(exc),
            "has_live_games": "false",
            "next_scheduled_start_at": None,
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": _live_interval_seconds(league),
            "mode": "live",
        }
    finally:
        _set_fetch_telemetry_context(provider, None)
        db.close()
