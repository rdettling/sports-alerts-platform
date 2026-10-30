from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Literal

from sqlalchemy import select

from app.db.models import CompetitionTeam, Game, GameOddsCurrent, OddsApiDailyUsage, Team
from app.db.session import SessionLocal
from app.schemas.schedule import OddsSyncOutcome
from app.services.competitions import get_active_competitions
from app.worker import odds
from app.config import settings

logger = logging.getLogger(__name__)

ODDS_DAILY_CREDIT_CAP = 16
ODDS_CREDIT_RESERVE = 25
ODDS_WINDOW = timedelta(hours=48)


@dataclass(frozen=True)
class OddsSyncResult:
    competition: str
    games_checked: int
    odds_snapshots_created: int
    outcome: OddsSyncOutcome = "fetched"


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _eligible_games_query(competition: str, now: datetime):
    return (
        select(Game)
        .outerjoin(GameOddsCurrent, GameOddsCurrent.game_id == Game.id)
        .where(
            Game.competition == competition,
            Game.is_odds_eligible.is_(True),
            Game.status == "scheduled",
            Game.is_final.is_(False),
            Game.scheduled_start_time > now,
            Game.scheduled_start_time <= now + ODDS_WINDOW,
            GameOddsCurrent.id.is_(None),
        )
        .order_by(Game.scheduled_start_time)
    )


def has_eligible_games(competition: str, now: datetime) -> bool:
    with SessionLocal() as db:
        return db.scalar(
            _eligible_games_query(competition, _as_utc(now)).with_only_columns(Game.id).limit(1)
        ) is not None


def next_eligible_start(competition: str, now: datetime) -> datetime | None:
    with SessionLocal() as db:
        return db.scalar(
            _eligible_games_query(competition, _as_utc(now)).with_only_columns(Game.scheduled_start_time).limit(1)
        )


def _log_request_failure(
    stage: str, competition: str, started_at: float, exc: Exception, games_checked: int | None = None,
) -> None:
    logger.warning(
        "Odds request failed stage=%s competition=%s games_checked=%s duration_ms=%s timeout_seconds=%s error_type=%s reason_type=%s http_status=%s",
        stage, competition, games_checked, int((monotonic() - started_at) * 1000),
        odds.ODDS_TIMEOUT_SECONDS, type(exc).__name__,
        type(exc.reason).__name__ if hasattr(exc, "reason") else None,
        getattr(exc, "code", None),
    )


def _reserve_credit(competition: str, now: datetime) -> Literal["allowed", "budget_limited", "quota_failed"]:
    with SessionLocal() as db:
        usage = db.get(OddsApiDailyUsage, now.date())
        if usage is not None and usage.credits_used >= ODDS_DAILY_CREDIT_CAP:
            return "budget_limited"
    started_at = monotonic()
    try:
        status = odds.fetch_quota_status()
    except Exception as exc:
        _log_request_failure("quota", competition, started_at, exc)
        return "quota_failed"
    with SessionLocal() as db:
        usage = db.get(OddsApiDailyUsage, now.date())
        if usage is None:
            usage = OddsApiDailyUsage(usage_date=now.date(), credits_used=0)
            db.add(usage)
        usage.provider_credits_used = status.credits_used
        usage.provider_credits_remaining = status.credits_remaining
        usage.provider_observed_at = now
        limited = status.credits_remaining is not None and status.credits_remaining <= ODDS_CREDIT_RESERVE
        if not limited:
            usage.credits_used += 1
        db.commit()
        return "budget_limited" if limited else "allowed"


def run_odds_sync(competition: str, now: datetime | None = None) -> OddsSyncResult:
    at = _as_utc(now or datetime.now(timezone.utc))
    with SessionLocal() as db:
        if competition not in get_active_competitions(db):
            raise ValueError(f"Competition disabled: {competition}")
        games = db.scalars(_eligible_games_query(competition, at)).all()
        if not games:
            return OddsSyncResult(competition, 0, 0, outcome="no_eligible_games")
        if not settings.odds_api_key.strip():
            return OddsSyncResult(competition, len(games), 0, outcome="missing_api_key")

    credit = _reserve_credit(competition, at)
    if credit != "allowed":
        return OddsSyncResult(competition, len(games), 0, outcome=credit)

    started_at = monotonic()
    try:
        response = odds.fetch_odds_with_usage(competition)
    except Exception as exc:
        _log_request_failure("prices", competition, started_at, exc, len(games))
        return OddsSyncResult(competition, len(games), 0, outcome="fetch_failed")

    with SessionLocal() as db:
        teams = {
            team.id: team.name
            for team in db.scalars(
                select(Team).where(
                    Team.id.in_({team_id for game in games for team_id in (game.home_team_id, game.away_team_id)})
                )
            ).all()
        }
        catalog_team_ids = set(
            db.scalars(
                select(CompetitionTeam.team_id).where(CompetitionTeam.competition == competition)
            ).all()
        )
        index = response.odds_index
        usage = db.get(OddsApiDailyUsage, at.date())
        if usage:
            usage.provider_credits_used = response.credits_used
            usage.provider_credits_remaining = response.credits_remaining
            usage.provider_observed_at = at

        snapshots = 0
        unmatched = 0
        unmatched_sample = []
        for game in games:
            home, away = teams.get(game.home_team_id), teams.get(game.away_team_id)
            selected = odds.select_best_for_game(
                index.get(odds.game_key(home, away)) if home and away else None,
                game.scheduled_start_time,
            )
            if selected is None and game.is_neutral_site and home and away:
                selected = odds.select_best_for_reversed_neutral_site_game(
                    index.get(odds.game_key(away, home)),
                    game.scheduled_start_time,
                    odds.team_key(home),
                    odds.team_key(away),
                )
            if selected is None and competition in {"FBS", "NCAAB"}:
                selected = odds.select_best_for_single_team(
                    index,
                    tuple(
                        odds.team_key(teams[team_id])
                        for team_id in (game.home_team_id, game.away_team_id)
                        if team_id in catalog_team_ids and team_id in teams
                    ),
                    game.scheduled_start_time,
                )
            if selected is not None:
                snapshots += int(odds.upsert_game_odds(db, game.id, selected))
            else:
                unmatched += 1
                if len(unmatched_sample) < 5:
                    unmatched_sample.append({
                        "game_id": game.id,
                        "home": home,
                        "away": away,
                        "start": game.scheduled_start_time.isoformat(),
                    })
        db.commit()
        logger.info(
            "Odds coverage competition=%s provider_moneyline_matchups=%s games_checked=%s odds_snapshots_created=%s unmatched_games=%s unmatched_sample=%s",
            competition, len(index), len(games), snapshots, unmatched, unmatched_sample,
        )
        return OddsSyncResult(competition, len(games), snapshots)
