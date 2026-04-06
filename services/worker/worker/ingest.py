from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Game, IngestRun, SentAlert, Team, UserAlertPreference, UserGameFollow, UserTeamFollow
from worker.config import settings
from worker.providers.base import NbaProvider, ProviderGame

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _team_id_map(db: Session) -> dict[str, int]:
    rows = db.scalars(select(Team)).all()
    return {team.external_team_id: team.id for team in rows}


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


def run_ingest_cycle(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    ingest_run = IngestRun(status="running", games_checked=0, games_updated=0)
    db.add(ingest_run)
    db.commit()
    db.refresh(ingest_run)

    try:
        team_map = _team_id_map(db)
        schedule = provider.fetch_schedule()
        tracked_game_ids = db.scalars(
            select(Game.external_game_id).where(Game.league == "NBA", Game.is_final.is_(False))
        ).all()
        updates = provider.fetch_game_updates([game_id for game_id in tracked_game_ids if game_id])
        games_by_id = {game.external_game_id: game for game in schedule}
        for game in updates:
            games_by_id[game.external_game_id] = game
        all_games = list(games_by_id.values())

        checked = len(all_games)
        updated = 0
        alert_records_created = 0
        touched_game_ids: list[int] = []
        for provider_game in all_games:
            did_update, game_id = _upsert_game(db, provider_game, team_map)
            if did_update:
                updated += 1
            if game_id:
                touched_game_ids.append(game_id)

        db.flush()
        for game_id in touched_game_ids:
            game = db.get(Game, game_id)
            if not game:
                continue
            alert_records_created += _evaluate_and_record_alerts(db, game)

        db.commit()
        logger.info(
            "Ingest cycle checked=%s updated=%s tracked=%s alerts_created=%s",
            checked,
            updated,
            len(tracked_game_ids),
            alert_records_created,
        )

        ingest_run.status = "success"
        ingest_run.games_checked = checked
        ingest_run.games_updated = updated
        ingest_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "success", "games_checked": checked, "games_updated": updated}
    except Exception as exc:
        db.rollback()
        ingest_run.status = "failed"
        ingest_run.error_message = str(exc)
        ingest_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.exception("Ingest cycle failed")
        return {"status": "failed", "games_checked": 0, "games_updated": 0}
    finally:
        db.close()
