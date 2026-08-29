from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CompetitionTeam, Game, Team
from app.db.session import SessionLocal
from app.services.competitions import competition_supports_odds, competition_teams_query, get_active_competitions, get_competition_profile, normalize_competition
from app.worker import odds, soccer
from app.worker.alerts import evaluate_and_record_alerts
from app.worker.cleanup import cleanup_games_outside_window
from app.worker.config import settings
from app.worker.planner import build_catalog_dates, build_live_requests
from app.worker.scoreboard import ScoreboardGame

logger = logging.getLogger(__name__)
LIVE_STATUS_RECHECK_GRACE = timedelta(hours=2)


class ScoreboardFetcher(Protocol):
    def fetch_games(self, competition: str, dates: list[str]) -> list[ScoreboardGame]: ...


@dataclass(frozen=True)
class GameUpdateResult:
    did_update: bool
    game_id: int | None
    soccer_events: soccer.SoccerDerivedEvents | None = None


@dataclass(frozen=True)
class CatalogSyncResult:
    competition: str
    games_checked: int
    games_updated: int
    alerts_created: int
    odds_candidates: int
    odds_snapshots_created: int
    games_removed: int
    next_live_sync_at: datetime | None


@dataclass(frozen=True)
class LiveSyncResult:
    competition: str
    games_checked: int
    games_updated: int
    alerts_created: int
    has_live_games: bool
    next_scheduled_start_at: datetime | None


def _assert_competition_enabled(db: Session, competition: str) -> None:
    if competition not in set(get_active_competitions(db)):
        raise ValueError(f"Competition disabled: {competition}")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _next_scheduled_start(db: Session, competition: str, now: datetime) -> datetime | None:
    return db.scalar(
        select(func.min(Game.scheduled_start_time)).where(
            Game.competition == competition,
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now - LIVE_STATUS_RECHECK_GRACE,
        )
    )


def _competition_team_maps(db: Session, competition: str) -> tuple[dict[str, int], dict[int, str]]:
    rows = db.scalars(competition_teams_query(competition)).all()
    return (
        {team.external_team_id: team.id for team in rows},
        {team.id: team.name for team in rows},
    )


def _register_fbs_opponents(
    db: Session,
    scoreboard_games: list[ScoreboardGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
) -> None:
    for game in scoreboard_games:
        provider_teams = (
            (
                game.home_external_team_id,
                game.home_team_name,
                game.home_team_abbreviation,
            ),
            (
                game.away_external_team_id,
                game.away_team_name,
                game.away_team_abbreviation,
            ),
        )
        for external_team_id, name, abbreviation in provider_teams:
            if external_team_id in team_map or not name or not abbreviation:
                continue
            team = db.scalar(
                select(Team).where(
                    Team.provider_scope == "cfb",
                    Team.external_team_id == external_team_id,
                )
            )
            if team is None:
                team = Team(
                    sport="football",
                    provider_scope="cfb",
                    external_team_id=external_team_id,
                    name=name,
                    abbreviation=abbreviation,
                )
                db.add(team)
                db.flush()
            db.add(CompetitionTeam(competition="FBS", team_id=team.id))
            team_map[external_team_id] = team.id
            team_names[team.id] = team.name
    db.flush()


def _upsert_game(db: Session, competition: str, payload: ScoreboardGame, team_map: dict[str, int]) -> GameUpdateResult:
    home_id = team_map.get(payload.home_external_team_id)
    away_id = team_map.get(payload.away_external_team_id)
    if not home_id or not away_id:
        logger.warning(
            "Skipping game due to missing teams competition=%s external_game_id=%s home_external_team_id=%s away_external_team_id=%s",
            competition,
            payload.external_game_id,
            payload.home_external_team_id,
            payload.away_external_team_id,
        )
        return GameUpdateResult(did_update=False, game_id=None)

    existing = db.scalar(select(Game).where(Game.external_game_id == payload.external_game_id, Game.competition == competition))
    if existing:
        is_soccer = get_competition_profile(competition).sport == "soccer"
        previous_snapshot = soccer.snapshot_state(existing) if is_soccer else None
        soccer_events = soccer.classify_events(existing, payload) if is_soccer else None
        state_before = (
            existing.context_label,
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        record_before = (existing.home_team_record, existing.away_team_record)
        existing.context_label = payload.context_label
        if payload.home_team_record is not None:
            existing.home_team_record = payload.home_team_record
        if payload.away_team_record is not None:
            existing.away_team_record = payload.away_team_record
        existing.status = payload.status
        existing.home_score = payload.home_score
        existing.away_score = payload.away_score
        existing.period = payload.period
        existing.clock = payload.clock
        existing.is_final = payload.is_final
        existing.last_ingested_at = datetime.now(timezone.utc)
        state_after = (
            existing.context_label,
            existing.status,
            existing.home_score,
            existing.away_score,
            existing.period,
            existing.clock,
            existing.is_final,
        )
        record_after = (existing.home_team_record, existing.away_team_record)
        state_changed = state_before != state_after
        records_changed = record_before != record_after
        if previous_snapshot is not None and state_changed:
            soccer.log_transition(previous_snapshot, payload, soccer_events)
        return GameUpdateResult(
            did_update=state_changed or records_changed,
            game_id=existing.id,
            soccer_events=soccer_events,
        )

    created = Game(
        external_game_id=payload.external_game_id,
        competition=competition,
        home_team_id=home_id,
        away_team_id=away_id,
        scheduled_start_time=payload.scheduled_start_time,
        context_label=payload.context_label,
        home_team_record=payload.home_team_record,
        away_team_record=payload.away_team_record,
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
    competition: str,
    scoreboard_games: list[ScoreboardGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
    *,
    only_external_ids: set[str] | None = None,
) -> tuple[int, list[int], dict[int, tuple[str, str]], dict[int, soccer.SoccerDerivedEvents]]:
    if competition == "FBS":
        _register_fbs_opponents(db, scoreboard_games, team_map, team_names)
    updated = 0
    touched_game_ids: list[int] = []
    game_key_by_id: dict[int, tuple[str, str]] = {}
    soccer_events: dict[int, soccer.SoccerDerivedEvents] = {}
    for scoreboard_game in scoreboard_games:
        if only_external_ids is not None and scoreboard_game.external_game_id not in only_external_ids:
            continue
        result = _upsert_game(db, competition, scoreboard_game, team_map)
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


def run_catalog_sync(provider: ScoreboardFetcher, competition: str = "NBA") -> CatalogSyncResult:
    competition = normalize_competition(competition)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _assert_competition_enabled(db, competition)
        requests = build_catalog_dates(now)
        team_map, team_names = _competition_team_maps(db, competition)
        all_games = provider.fetch_games(competition, requests)
        updated, touched_game_ids, game_key_by_id, soccer_events = _upsert_games_and_collect(db, competition, all_games, team_map, team_names)
        if all_games and not touched_game_ids:
            raise RuntimeError(f"No {competition} games could be mapped to catalog teams")

        odds_eligible_external_ids = None
        if competition == "NFL":
            odds_eligible_external_ids = {
                game.external_game_id for game in all_games if game.season_slug != "preseason"
            }
        odds_candidates = (
            odds.games_missing_pregame_snapshot(
                db,
                competition,
                now,
                eligible_external_ids=odds_eligible_external_ids,
            )
            if settings.odds_api_key.strip() and competition_supports_odds(competition)
            else []
        )
        odds_snapshots_created = 0
        if odds_candidates:
            odds_by_matchup = odds.fetch_odds_index(competition)
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
        games_removed = cleanup_games_outside_window(db, now)
        has_live_games = bool(
            db.scalar(
                select(func.count(Game.id)).where(
                    Game.competition == competition,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live")),
                )
            )
            or 0
        )
        next_live_sync_at = now if has_live_games else _as_utc(_next_scheduled_start(db, competition, now))
        db.commit()

        return CatalogSyncResult(
            competition=competition,
            games_checked=len(all_games),
            games_updated=updated,
            alerts_created=alerts_created,
            odds_candidates=len(odds_candidates),
            odds_snapshots_created=odds_snapshots_created,
            games_removed=games_removed,
            next_live_sync_at=next_live_sync_at,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_live_sync(provider: ScoreboardFetcher, competition: str = "NBA") -> LiveSyncResult:
    competition = normalize_competition(competition)
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        _assert_competition_enabled(db, competition)
        requests = build_live_requests(db, competition)
        if not requests:
            return LiveSyncResult(
                competition=competition,
                games_checked=0,
                games_updated=0,
                alerts_created=0,
                has_live_games=False,
                next_scheduled_start_at=_as_utc(_next_scheduled_start(db, competition, now)),
            )

        team_map, team_names = _competition_team_maps(db, competition)
        provider_games = provider.fetch_games(competition, requests)
        candidate_ids = {
            external_id
            for external_id, in db.execute(
                select(Game.external_game_id).where(
                    Game.competition == competition,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live", "scheduled")),
                )
            ).all()
        }
        updated, touched_game_ids, _, soccer_events = _upsert_games_and_collect(
            db,
            competition,
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
                    Game.competition == competition,
                    Game.is_final.is_(False),
                    Game.status.in_(("in_progress", "live")),
                )
            )
            or 0
        )
        next_scheduled = _as_utc(_next_scheduled_start(db, competition, now))
        db.commit()
        return LiveSyncResult(
            competition=competition,
            games_checked=len(provider_games),
            games_updated=updated,
            alerts_created=alerts_created,
            has_live_games=has_live_games,
            next_scheduled_start_at=next_scheduled,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
