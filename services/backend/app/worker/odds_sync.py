from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import CompetitionTeam, Game, GameOddsCurrent, OddsApiDailyUsage, Team
from app.db.session import SessionLocal
from app.services.competitions import get_active_competitions
from app.worker import odds
from app.worker.config import settings

ODDS_DAILY_CREDIT_CAP = 16
ODDS_CREDIT_RESERVE = 25
ODDS_WINDOW = timedelta(hours=48)


@dataclass(frozen=True)
class OddsSyncResult:
    competition: str
    games_checked: int
    odds_snapshots_created: int
    budget_limited: bool = False


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _eligible_games(db, competition: str, now: datetime) -> list[Game]:
    return list(
        db.scalars(
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
        ).all()
    )


def has_eligible_games(competition: str, now: datetime) -> bool:
    with SessionLocal() as db:
        return bool(_eligible_games(db, competition, _as_utc(now)))


def next_eligible_start(competition: str, now: datetime) -> datetime | None:
    with SessionLocal() as db:
        games = _eligible_games(db, competition, _as_utc(now))
        return games[0].scheduled_start_time if games else None


def _reserve_credit(db, now: datetime) -> tuple[bool, bool]:
    usage = db.get(OddsApiDailyUsage, now.date())
    if usage is None:
        usage = OddsApiDailyUsage(usage_date=now.date())
        db.add(usage)
        db.flush()
    if usage.credits_used >= ODDS_DAILY_CREDIT_CAP:
        return False, True
    try:
        status = odds.fetch_quota_status()
    except Exception:
        return False, False
    usage.provider_credits_used = status.credits_used
    usage.provider_credits_remaining = status.credits_remaining
    usage.provider_observed_at = now
    if status.credits_remaining is not None and status.credits_remaining <= ODDS_CREDIT_RESERVE:
        db.commit()
        return False, True
    usage.credits_used += 1
    db.commit()
    return True, False


def run_odds_sync(competition: str, now: datetime | None = None) -> OddsSyncResult:
    at = _as_utc(now or datetime.now(timezone.utc))
    with SessionLocal() as db:
        if competition not in get_active_competitions(db):
            raise ValueError(f"Competition disabled: {competition}")
        games = _eligible_games(db, competition, at)
        if not games or not settings.odds_api_key.strip():
            return OddsSyncResult(competition, 0, 0)

        allowed, limited = _reserve_credit(db, at)
        if not allowed:
            return OddsSyncResult(competition, 0, 0, limited)

        try:
            response = odds.fetch_odds_with_usage(competition)
        except Exception:
            response = None

        teams = {
            team.id: team.name
            for team in db.scalars(
                select(Team).where(
                    Team.id.in_({team_id for game in games for team_id in (game.home_team_id, game.away_team_id)})
                )
            ).all()
        }
        fbs_ids = set(
            db.scalars(
                select(CompetitionTeam.team_id).where(CompetitionTeam.competition == competition)
            ).all()
        )
        index = response.odds_index if response else {}
        if response:
            usage = db.get(OddsApiDailyUsage, at.date())
            if usage:
                usage.provider_credits_used = response.credits_used
                usage.provider_credits_remaining = response.credits_remaining
                usage.provider_observed_at = at

        snapshots = 0
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
            if selected is None and competition == "FBS":
                selected = odds.select_best_for_single_team(
                    index,
                    tuple(
                        odds.team_key(teams[team_id])
                        for team_id in (game.home_team_id, game.away_team_id)
                        if team_id in fbs_ids and team_id in teams
                    ),
                    game.scheduled_start_time,
                )
            if selected is not None:
                snapshots += int(odds.upsert_game_odds(db, game.id, selected))
        db.commit()
        return OddsSyncResult(competition, len(games), snapshots)
