from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LeagueSetting


Sport = Literal["basketball", "baseball", "soccer"]


@dataclass(frozen=True)
class LeagueProfile:
    league: str
    sport: Sport
    label: str
    badge_label: str
    default_test_matchup: tuple[str, str]
    scoreboard_url: str
    live_sync_interval_seconds: int
    odds_sport_key: str | None


SPORT_ALERT_TYPES: dict[Sport, tuple[str, ...]] = {
    "basketball": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "baseball": ("game_start", "inning_start", "final_result"),
    "soccer": (
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    ),
}


LEAGUE_PROFILES: dict[str, LeagueProfile] = {
    "NBA": LeagueProfile(
        league="NBA",
        sport="basketball",
        label="NBA",
        badge_label="NBA",
        default_test_matchup=("ATL", "BOS"),
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        live_sync_interval_seconds=120,
        odds_sport_key="basketball_nba",
    ),
    "WNBA": LeagueProfile(
        league="WNBA",
        sport="basketball",
        label="WNBA",
        badge_label="WNBA",
        default_test_matchup=("NY", "LV"),
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
        live_sync_interval_seconds=120,
        odds_sport_key="basketball_wnba",
    ),
    "MLB": LeagueProfile(
        league="MLB",
        sport="baseball",
        label="MLB",
        badge_label="MLB",
        default_test_matchup=("MIA", "TOR"),
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        live_sync_interval_seconds=300,
        odds_sport_key="baseball_mlb",
    ),
    "MLS": LeagueProfile(
        league="MLS",
        sport="soccer",
        label="MLS",
        badge_label="MLS",
        default_test_matchup=("LAFC", "LA"),
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_usa_mls",
    ),
    "WORLD_CUP": LeagueProfile(
        league="WORLD_CUP",
        sport="soccer",
        label="World Cup",
        badge_label="WC",
        default_test_matchup=("MEX", "USA"),
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_fifa_world_cup",
    ),
}

LEAGUE_ORDER = tuple(LEAGUE_PROFILES.keys())


def list_supported_leagues() -> list[str]:
    return list(LEAGUE_ORDER)


def normalize_league(league: str) -> str:
    value = league.strip().upper()
    if value not in LEAGUE_PROFILES:
        raise ValueError(f"Unsupported league: {league}")
    return value


def get_league_profile(league: str) -> LeagueProfile:
    return LEAGUE_PROFILES[normalize_league(league)]


def get_alert_types(league: str) -> tuple[str, ...]:
    return SPORT_ALERT_TYPES[get_league_profile(league).sport]


def get_default_test_matchup(league: str) -> tuple[str, str]:
    return get_league_profile(league).default_test_matchup


def get_scoreboard_url(league: str) -> str:
    return get_league_profile(league).scoreboard_url


def league_supports_odds(league: str) -> bool:
    return get_league_profile(league).odds_sport_key is not None


def ensure_league_settings(db: Session) -> None:
    existing = {
        row.league
        for row in db.scalars(select(LeagueSetting).where(LeagueSetting.league.in_(LEAGUE_ORDER))).all()
    }
    if len(existing) == len(LEAGUE_ORDER):
        return

    now = datetime.now(timezone.utc)
    for league in LEAGUE_ORDER:
        if league in existing:
            continue
        db.add(LeagueSetting(league=league, is_enabled=True, created_at=now, updated_at=now))
    db.commit()


def list_league_settings(db: Session) -> list[LeagueSetting]:
    ensure_league_settings(db)
    rows = db.scalars(select(LeagueSetting).order_by(LeagueSetting.league.asc())).all()
    order = {league: index for index, league in enumerate(LEAGUE_ORDER)}
    return sorted(rows, key=lambda row: order.get(row.league, len(order)))


def get_active_leagues(db: Session) -> list[str]:
    return [row.league for row in list_league_settings(db) if row.is_enabled]


def is_league_enabled(db: Session, league: str) -> bool:
    normalized = normalize_league(league)
    return normalized in set(get_active_leagues(db))
