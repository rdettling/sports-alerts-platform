from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Game,
    GameOddsCurrent,
    GameOddsOutcomeCurrent,
    Team,
)
from app.services.leagues import get_active_leagues, get_league_profile, league_supports_odds, list_supported_leagues
from worker.alerts import ScoreChangeEvent, SoccerDerivedEvents, evaluate_and_record_alerts
from worker.db import SessionLocal
from worker.config import settings
from worker.odds import OddsSnapshot, fetch_odds_index, game_key, set_telemetry_context as set_odds_telemetry_context
from worker.planner import build_catalog_requests, build_live_requests
from worker.scoreboard import ScoreboardGame

logger = logging.getLogger(__name__)
ODDS_MATCH_MAX_COMMENCE_DIFF = timedelta(hours=18)
LIVE_STATUS_RECHECK_GRACE = timedelta(hours=2)
SUPPORTED_LEAGUES = tuple(list_supported_leagues())


class ScoreboardFetcher(Protocol):
    def fetch_games(self, league: str, dates: list[str]) -> list[ScoreboardGame]: ...


@dataclass(frozen=True)
class GameUpdateResult:
    did_update: bool
    game_id: int | None
    soccer_events: SoccerDerivedEvents | None = None


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


def _is_soccer_live_second_half(*, status: str, period: int | None, clock: str | None) -> bool:
    if status not in {"in_progress", "live"}:
        return False
    if period != 2:
        return False
    normalized_clock = (clock or "").strip().upper()
    return normalized_clock not in {"HT", "HALFTIME"}


def _is_soccer_extra_time(*, status: str, period: int | None) -> bool:
    return status in {"in_progress", "live"} and period in {3, 4}


def _is_soccer_penalty_kicks_window(*, status: str, period: int | None, home_score: int | None, away_score: int | None, clock: str | None) -> bool:
    if status not in {"in_progress", "live"}:
        return False
    if home_score is None or away_score is None or home_score != away_score:
        return False
    if (period or 0) >= 5:
        return True
    if not _is_soccer_extra_time(status=status, period=period):
        return False
    if not clock:
        return False
    text = clock.strip().replace("'", "")
    if not text:
        return False
    minute_text = text.split("+", 1)[0].strip()
    try:
        return int(minute_text) >= 117
    except ValueError:
        return False


@dataclass(frozen=True)
class SoccerStateSnapshot:
    external_game_id: str
    context_label: str | None
    status: str
    home_score: int | None
    away_score: int | None
    period: int | None
    clock: str | None
    is_final: bool


def _soccer_state_snapshot(game: Game) -> SoccerStateSnapshot:
    return SoccerStateSnapshot(
        external_game_id=game.external_game_id,
        context_label=game.context_label,
        status=game.status,
        home_score=game.home_score,
        away_score=game.away_score,
        period=game.period,
        clock=game.clock,
        is_final=game.is_final,
    )


def _classify_soccer_derived_events(previous: Game | None, payload: ScoreboardGame) -> SoccerDerivedEvents | None:
    if previous is None:
        return None
    score_change: ScoreChangeEvent | None = None
    if (
        payload.status in {"in_progress", "live"}
        and (payload.period or 0) < 5
        and previous.home_score is not None
        and previous.away_score is not None
        and payload.home_score is not None
        and payload.away_score is not None
    ):
        home_delta = payload.home_score - previous.home_score
        away_delta = payload.away_score - previous.away_score
        if not (home_delta == 0 and away_delta == 0) and not (home_delta < 0 or away_delta < 0):
            if home_delta == 0 and away_delta == 1:
                scoring_side = "away"
                is_inferred_goal = True
            elif away_delta == 0 and home_delta == 1:
                scoring_side = "home"
                is_inferred_goal = True
            else:
                scoring_side = None
                is_inferred_goal = False

            score_change = ScoreChangeEvent(
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

    second_half_started = (
        not payload.is_final
        and not _is_soccer_live_second_half(status=previous.status, period=previous.period, clock=previous.clock)
        and _is_soccer_live_second_half(status=payload.status, period=payload.period, clock=payload.clock)
    )
    extra_time_started = (
        not payload.is_final
        and not _is_soccer_extra_time(status=previous.status, period=previous.period)
        and _is_soccer_extra_time(status=payload.status, period=payload.period)
    )
    if score_change is None and not second_half_started and not extra_time_started:
        return None
    return SoccerDerivedEvents(
        score_change=score_change,
        second_half_started=second_half_started,
        extra_time_started=extra_time_started,
    )


def _log_soccer_transition(previous: SoccerStateSnapshot, payload: ScoreboardGame, events: SoccerDerivedEvents | None) -> None:
    previous_second_half = _is_soccer_live_second_half(status=previous.status, period=previous.period, clock=previous.clock)
    new_second_half = _is_soccer_live_second_half(status=payload.status, period=payload.period, clock=payload.clock)
    previous_extra_time = _is_soccer_extra_time(status=previous.status, period=previous.period)
    new_extra_time = _is_soccer_extra_time(status=payload.status, period=payload.period)
    previous_penalty_kicks_window = _is_soccer_penalty_kicks_window(
        status=previous.status,
        period=previous.period,
        home_score=previous.home_score,
        away_score=previous.away_score,
        clock=previous.clock,
    )
    new_penalty_kicks_window = _is_soccer_penalty_kicks_window(
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
        previous_snapshot = _soccer_state_snapshot(existing) if is_soccer else None
        soccer_events = _classify_soccer_derived_events(existing, payload) if is_soccer else None
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
            _log_soccer_transition(previous_snapshot, payload, soccer_events)
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


def _odds_signature(odds: OddsSnapshot) -> tuple[tuple[str, str | None, int | None, str | None], ...]:
    return tuple(
        (outcome.outcome_key, outcome.team_side, outcome.price_american, outcome.outcome_label)
        for outcome in odds.outcomes
    )


def _stored_odds_signature(row: GameOddsCurrent) -> tuple[tuple[str, str | None, int | None, str | None], ...]:
    return tuple(
        (outcome.outcome_key, outcome.team_side, outcome.price_american, outcome.outcome_label)
        for outcome in sorted(row.outcomes, key=lambda outcome: outcome.outcome_order)
    )


def _build_current_odds_outcomes(odds: OddsSnapshot) -> list[GameOddsOutcomeCurrent]:
    return [
        GameOddsOutcomeCurrent(
            outcome_key=outcome.outcome_key,
            outcome_label=outcome.outcome_label,
            outcome_order=outcome.outcome_order,
            price_american=outcome.price_american,
            team_side=outcome.team_side,
        )
        for outcome in odds.outcomes
    ]


def _upsert_game_odds(db: Session, game_id: int, odds: OddsSnapshot) -> bool:
    row = db.scalar(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id == game_id,
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == odds.market,
        )
    )
    if row:
        before = (row.bookmaker, _stored_odds_signature(row))
        after = (odds.bookmaker, _odds_signature(odds))
        if before == after:
            return False
        row.bookmaker = odds.bookmaker
        row.fetched_at = odds.last_update or datetime.now(timezone.utc)
        row.outcomes.clear()
        row.outcomes.extend(_build_current_odds_outcomes(odds))
        return True

    row = GameOddsCurrent(
        game_id=game_id,
        provider=settings.odds_provider,
        market=odds.market,
        bookmaker=odds.bookmaker,
        fetched_at=odds.last_update or datetime.now(timezone.utc),
    )
    row.outcomes.extend(_build_current_odds_outcomes(odds))
    db.add(row)
    return True

def _select_best_odds_for_game(
    options: list[OddsSnapshot] | OddsSnapshot | None,
    scheduled_start_time: datetime,
) -> OddsSnapshot | None:
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


def _upsert_games_and_collect(
    db: Session,
    league: str,
    scoreboard_games: list[ScoreboardGame],
    team_map: dict[str, int],
    team_names: dict[int, str],
    *,
    only_external_ids: set[str] | None = None,
) -> tuple[int, list[int], dict[int, tuple[str, str]], dict[int, SoccerDerivedEvents]]:
    updated = 0
    touched_game_ids: list[int] = []
    game_key_by_id: dict[int, tuple[str, str]] = {}
    soccer_events: dict[int, SoccerDerivedEvents] = {}
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
                game_key_by_id[result.game_id] = game_key(home_name, away_name)
            if result.soccer_events is not None:
                soccer_events[result.game_id] = result.soccer_events
    return updated, touched_game_ids, game_key_by_id, soccer_events


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


def _set_fetch_telemetry_context(provider: ScoreboardFetcher, db: Session | None) -> None:
    provider_context = getattr(provider, "set_telemetry_context", None)
    if callable(provider_context):
        provider_context(db, None)
    set_odds_telemetry_context(db, None)


def run_catalog_sync(provider: ScoreboardFetcher, league: str = "NBA") -> dict[str, int | str]:
    league = _normalize_league(league)
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
            "next_poll_seconds": _catalog_interval_seconds(league),
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
            "next_poll_seconds": _catalog_interval_seconds(league),
        }
    finally:
        _set_fetch_telemetry_context(provider, None)
        db.close()


def run_live_sync(provider: ScoreboardFetcher, league: str = "NBA") -> dict[str, int | str]:
    league = _normalize_league(league)
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
                "next_poll_seconds": _catalog_interval_seconds(league),
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
            "next_poll_seconds": _live_interval_seconds(league) if has_live_games else _catalog_interval_seconds(league),
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
