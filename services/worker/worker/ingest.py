from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Game,
    GameOddsCurrent,
    IngestRun,
    SentAlert,
    Team,
    UserAlertPreference,
    UserGameFollow,
    UserTeamFollow,
)
from worker.delivery import process_pending_alerts
from worker.config import settings
from worker.odds import MoneylineOdds, fetch_nba_odds_index, game_key
from worker.providers.base import NbaProvider, ProviderGame

logger = logging.getLogger(__name__)
ODDS_MATCH_MAX_COMMENCE_DIFF = timedelta(hours=18)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


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


def _recommended_poll_interval_seconds(db: Session) -> int:
    now = datetime.now(timezone.utc)
    live_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
            Game.is_final.is_(False),
            Game.status.in_(("in_progress", "live")),
        )
    ) or 0
    if live_count > 0:
        return max(15, settings.worker_poll_interval_live_seconds)

    soon_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
            Game.is_final.is_(False),
            Game.status == "scheduled",
            Game.scheduled_start_time >= now - timedelta(minutes=30),
            Game.scheduled_start_time <= now + timedelta(hours=2),
        )
    ) or 0
    if soon_count > 0:
        return max(30, settings.worker_poll_interval_soon_seconds)

    same_day_count = db.scalar(
        select(func.count(Game.id)).where(
            Game.league == "NBA",
            Game.is_final.is_(False),
            Game.scheduled_start_time >= now - timedelta(hours=12),
            Game.scheduled_start_time <= now + timedelta(hours=24),
        )
    ) or 0
    if same_day_count > 0:
        return max(60, settings.worker_poll_interval_day_seconds)

    return max(60, settings.worker_poll_interval_idle_seconds)


def run_ingest_cycle(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    ingest_run = IngestRun(status="running", games_checked=0, games_updated=0)
    db.add(ingest_run)
    db.commit()
    db.refresh(ingest_run)

    try:
        team_map = _team_id_map(db)
        team_names = _team_name_map(db)
        schedule = provider.fetch_schedule()
        tracked_game_ids = db.scalars(
            select(Game.external_game_id).where(
                Game.league == "NBA",
                Game.is_final.is_(False),
                or_(
                    Game.status.in_(("in_progress", "live")),
                    Game.scheduled_start_time >= datetime.now(timezone.utc) - timedelta(hours=6),
                ),
            )
        ).all()
        schedule_game_ids = {game.external_game_id for game in schedule}
        missing_tracked_ids = [game_id for game_id in tracked_game_ids if game_id and game_id not in schedule_game_ids]
        updates = provider.fetch_game_updates(missing_tracked_ids) if missing_tracked_ids else []
        games_by_id = {game.external_game_id: game for game in schedule}
        for game in updates:
            games_by_id[game.external_game_id] = game
        all_games = list(games_by_id.values())

        checked = len(all_games)
        updated = 0
        alert_records_created = 0
        odds_updated = 0
        odds_by_matchup = fetch_nba_odds_index()
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

        delivery_sent, delivery_failed = process_pending_alerts(db)
        db.commit()
        logger.info(
            "Ingest cycle checked=%s updated=%s tracked=%s odds_updated=%s alerts_created=%s delivery_sent=%s delivery_failed=%s",
            checked,
            updated,
            len(tracked_game_ids),
            odds_updated,
            alert_records_created,
            delivery_sent,
            delivery_failed,
        )

        ingest_run.status = "success"
        ingest_run.games_checked = checked
        ingest_run.games_updated = updated
        ingest_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        next_poll = _recommended_poll_interval_seconds(db)
        return {"status": "success", "games_checked": checked, "games_updated": updated, "next_poll_seconds": next_poll}
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
            "next_poll_seconds": settings.worker_poll_interval_seconds,
        }
    finally:
        db.close()
