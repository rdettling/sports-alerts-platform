from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Game, IngestRun, Team
from worker.config import settings
from worker.providers.base import NbaProvider, ProviderGame

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _team_id_map(db: Session) -> dict[str, int]:
    rows = db.scalars(select(Team)).all()
    return {team.external_team_id: team.id for team in rows}


def _upsert_game(db: Session, payload: ProviderGame, team_map: dict[str, int]) -> bool:
    home_id = team_map.get(payload.home_external_team_id)
    away_id = team_map.get(payload.away_external_team_id)
    if not home_id or not away_id:
        logger.warning("Skipping game %s due to missing teams", payload.external_game_id)
        return False

    existing = db.scalar(select(Game).where(Game.external_game_id == payload.external_game_id, Game.league == "NBA"))
    if existing:
        existing.status = payload.status
        existing.home_score = payload.home_score
        existing.away_score = payload.away_score
        existing.period = payload.period
        existing.clock = payload.clock
        existing.is_final = payload.is_final
        existing.last_ingested_at = datetime.now(timezone.utc)
        return True

    db.add(
        Game(
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
    )
    return True


def run_ingest_cycle(provider: NbaProvider) -> dict[str, int | str]:
    db = SessionLocal()
    ingest_run = IngestRun(status="running", games_checked=0, games_updated=0)
    db.add(ingest_run)
    db.commit()
    db.refresh(ingest_run)

    try:
        team_map = _team_id_map(db)
        schedule = provider.fetch_schedule()
        checked = len(schedule)
        updated = 0
        for provider_game in schedule:
            if _upsert_game(db, provider_game, team_map):
                updated += 1
        db.commit()

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
