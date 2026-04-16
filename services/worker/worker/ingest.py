from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    ApiCallEvent,
    Game,
    GameOddsCurrent,
    IngestRun,
    SentAlert,
    Team,
    UserAlertPreference,
    UserGameFollow,
    UserTeamFollow,
)
from worker.db import SessionLocal
from worker.config import settings
from worker.odds import MoneylineOdds, fetch_nba_odds_index, game_key, set_telemetry_context as set_odds_telemetry_context
from worker.planner import build_fetch_plan
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


def _active_user_ids_for_game(db: Session, game: Game) -> list[int]:
    rows = db.execute(
        select(UserTeamFollow.user_id, UserGameFollow.user_id)
        .select_from(Game)
        .outerjoin(UserTeamFollow, or_(UserTeamFollow.team_id == Game.home_team_id, UserTeamFollow.team_id == Game.away_team_id))
        .outerjoin(UserGameFollow, UserGameFollow.game_id == Game.id)
        .where(Game.id == game.id)
    ).all()
    user_ids: set[int] = set()
    for team_user_id, game_user_id in rows:
        if team_user_id:
            user_ids.add(team_user_id)
        if game_user_id:
            user_ids.add(game_user_id)
    return sorted(user_ids)


def _preference_for_user(
    db: Session,
    user_id: int,
    alert_type: str,
) -> UserAlertPreference | None:
    return db.scalar(
        select(UserAlertPreference).where(
            UserAlertPreference.user_id == user_id,
            UserAlertPreference.alert_type == alert_type,
            UserAlertPreference.is_enabled.is_(True),
        )
    )


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


def _create_sent_alert(
    db: Session,
    user_id: int,
    game: Game,
    alert_type: str,
    metadata: dict[str, str | int | bool],
) -> bool:
    dedupe_key = f"{user_id}:{game.id}:{alert_type}"
    existing = db.scalar(select(SentAlert.id).where(SentAlert.dedupe_key == dedupe_key))
    if existing:
        return False
    db.add(
        SentAlert(
            user_id=user_id,
            game_id=game.id,
            alert_type=alert_type,
            delivery_channel="email",
            delivery_status="pending",
            dedupe_key=dedupe_key,
            metadata_json=metadata,
        )
    )
    db.flush()
    return True


def _evaluate_and_record_alerts(db: Session, game: Game) -> int:
    user_ids = _active_user_ids_for_game(db, game)
    created = 0
    for user_id in user_ids:
        game_start_pref = _preference_for_user(db, user_id, "game_start")
        if game_start_pref and game.status in {"in_progress", "live"}:
            if _create_sent_alert(
                db,
                user_id=user_id,
                game=game,
                alert_type="game_start",
                metadata={"status": game.status},
            ):
                created += 1

        final_pref = _preference_for_user(db, user_id, "final_result")
        if final_pref and (game.is_final or game.status == "final"):
            if _create_sent_alert(
                db,
                user_id=user_id,
                game=game,
                alert_type="final_result",
                metadata={"status": game.status},
            ):
                created += 1

        close_pref = _preference_for_user(db, user_id, "close_game_late")
        if _should_trigger_close_game_late(game, close_pref):
            if _create_sent_alert(
                db,
                user_id=user_id,
                game=game,
                alert_type="close_game_late",
                metadata={"period": game.period or 0, "clock": game.clock or "", "status": game.status},
            ):
                created += 1
    return created


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


def _upsert_game_odds(db: Session, game_id: int, odds: MoneylineOdds) -> None:
    row = db.scalar(
        select(GameOddsCurrent).where(
            GameOddsCurrent.game_id == game_id,
            GameOddsCurrent.provider == settings.odds_provider,
            GameOddsCurrent.market == settings.odds_api_market,
        )
    )
    if row:
        row.home_moneyline = odds.home_moneyline
        row.away_moneyline = odds.away_moneyline
        row.bookmaker = odds.bookmaker
        row.fetched_at = odds.last_update or datetime.now(timezone.utc)
        return

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


def run_ingest_cycle(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    plan = build_fetch_plan(db)
    ingest_run = IngestRun(status="running", games_checked=0, games_updated=0, poll_mode=plan.mode)
    db.add(ingest_run)
    db.commit()
    db.refresh(ingest_run)
    if hasattr(provider, "set_telemetry_context"):
        provider.set_telemetry_context(db, ingest_run.id)  # type: ignore[attr-defined]
    set_odds_telemetry_context(db, ingest_run.id)

    try:
        team_map = _team_id_map(db)
        team_names = _team_name_map(db)
        all_games = provider.fetch_games(plan.espn_requests)

        checked = len(all_games)
        updated = 0
        alert_records_created = 0
        odds_updated = 0
        touched_game_ids: list[int] = []
        game_key_by_id: dict[int, tuple[str, str]] = {}
        for provider_game in all_games:
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

        odds_by_matchup: dict[tuple[str, str], list[MoneylineOdds]] = {}
        if plan.odds_refresh:
            odds_by_matchup = fetch_nba_odds_index()

        for game_id, key in game_key_by_id.items():
            game = db.get(Game, game_id)
            if not game:
                continue
            matchup_odds = odds_by_matchup.get(key)
            odds = _select_best_odds_for_game(matchup_odds, game.scheduled_start_time)
            if not odds:
                if matchup_odds:
                    _delete_game_odds(db, game_id)
                continue
            _upsert_game_odds(db, game_id, odds)
            odds_updated += 1

        db.flush()
        for game_id in touched_game_ids:
            game = db.get(Game, game_id)
            if not game:
                continue
            alert_records_created += _evaluate_and_record_alerts(db, game)

        actual_espn_calls = db.scalar(
            select(func.count(ApiCallEvent.id)).where(
                ApiCallEvent.ingest_run_id == ingest_run.id,
                ApiCallEvent.provider == "espn",
            )
        ) or 0
        actual_odds_calls = db.scalar(
            select(func.count(ApiCallEvent.id)).where(
                ApiCallEvent.ingest_run_id == ingest_run.id,
                ApiCallEvent.provider == "odds",
            )
        ) or 0
        expected_espn_calls = provider.expected_call_count(plan.espn_requests)
        ingest_run.expected_espn_calls = expected_espn_calls
        ingest_run.expected_odds_calls = plan.expected_odds_calls
        ingest_run.actual_espn_calls = int(actual_espn_calls)
        ingest_run.actual_odds_calls = int(actual_odds_calls)
        db.commit()
        logger.info(
            "Ingest cycle mode=%s checked=%s updated=%s odds_refresh=%s(%s) odds_updated=%s alerts_created=%s",
            plan.mode,
            checked,
            updated,
            plan.odds_refresh,
            plan.odds_refresh_reason,
            odds_updated,
            alert_records_created,
        )

        ingest_run.status = "success"
        ingest_run.games_checked = checked
        ingest_run.games_updated = updated
        ingest_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "success",
            "games_checked": checked,
            "games_updated": updated,
            "next_poll_seconds": plan.next_ingest_seconds,
            "mode": plan.mode,
        }
    except Exception as exc:
        db.rollback()
        ingest_run.status = "failed"
        ingest_run.error_message = str(exc)
        ingest_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Ingest cycle failed")
        return {
            "status": "failed",
            "games_checked": 0,
            "games_updated": 0,
            "next_poll_seconds": settings.ingest_interval_active_seconds,
        }
    finally:
        if hasattr(provider, "set_telemetry_context"):
            provider.set_telemetry_context(None, None)  # type: ignore[attr-defined]
        set_odds_telemetry_context(None, None)
        db.close()
