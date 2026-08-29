from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompetitionSetting, CompetitionTeam, Team


Sport = Literal["basketball", "football", "baseball", "soccer"]


@dataclass(frozen=True)
class CompetitionProfile:
    competition: str
    sport: Sport
    provider_team_scope: str
    label: str
    badge_label: str
    scoreboard_url: str
    live_sync_interval_seconds: int
    odds_sport_key: str | None
    scoreboard_params: tuple[tuple[str, str], ...] = ()
    supported_alert_types: tuple[str, ...] | None = None


SPORT_ALERT_TYPES: dict[Sport, tuple[str, ...]] = {
    "basketball": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "football": ("game_start", "close_game_late", "overtime_start", "final_result"),
    "baseball": ("game_start", "inning_start", "extra_innings_start", "final_result"),
    "soccer": (
        "game_start",
        "second_half_start",
        "extra_time_start",
        "penalty_kicks",
        "score_changed",
        "final_result",
    ),
}
SPORT_ORDER = tuple(SPORT_ALERT_TYPES)


COMPETITION_PROFILES: dict[str, CompetitionProfile] = {
    "NBA": CompetitionProfile(
        competition="NBA",
        sport="basketball",
        provider_team_scope="nba",
        label="NBA",
        badge_label="NBA",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        live_sync_interval_seconds=120,
        odds_sport_key="basketball_nba",
    ),
    "WNBA": CompetitionProfile(
        competition="WNBA",
        sport="basketball",
        provider_team_scope="wnba",
        label="WNBA",
        badge_label="WNBA",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
        live_sync_interval_seconds=120,
        odds_sport_key="basketball_wnba",
    ),
    "NFL": CompetitionProfile(
        competition="NFL",
        sport="football",
        provider_team_scope="nfl",
        label="NFL",
        badge_label="NFL",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        live_sync_interval_seconds=120,
        odds_sport_key="americanfootball_nfl",
    ),
    "FBS": CompetitionProfile(
        competition="FBS",
        sport="football",
        provider_team_scope="cfb",
        label="College Football",
        badge_label="FBS",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
        scoreboard_params=(("groups", "80"), ("limit", "1000")),
        live_sync_interval_seconds=120,
        odds_sport_key="americanfootball_ncaaf",
    ),
    "MLB": CompetitionProfile(
        competition="MLB",
        sport="baseball",
        provider_team_scope="mlb",
        label="MLB",
        badge_label="MLB",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        live_sync_interval_seconds=300,
        odds_sport_key="baseball_mlb",
    ),
    "MLS": CompetitionProfile(
        competition="MLS",
        sport="soccer",
        provider_team_scope="soccer",
        label="MLS",
        badge_label="MLS",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_usa_mls",
    ),
    "LA_LIGA": CompetitionProfile(
        competition="LA_LIGA",
        sport="soccer",
        provider_team_scope="soccer",
        label="La Liga",
        badge_label="LALIGA",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_spain_la_liga",
        supported_alert_types=("game_start", "second_half_start", "score_changed", "final_result"),
    ),
    "PREMIER_LEAGUE": CompetitionProfile(
        competition="PREMIER_LEAGUE",
        sport="soccer",
        provider_team_scope="soccer",
        label="Premier League",
        badge_label="EPL",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_epl",
        supported_alert_types=("game_start", "second_half_start", "score_changed", "final_result"),
    ),
    "WORLD_CUP": CompetitionProfile(
        competition="WORLD_CUP",
        sport="soccer",
        provider_team_scope="soccer",
        label="World Cup",
        badge_label="WC",
        scoreboard_url="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
        live_sync_interval_seconds=180,
        odds_sport_key="soccer_fifa_world_cup",
    ),
}

COMPETITION_ORDER = tuple(COMPETITION_PROFILES.keys())


def list_supported_competitions() -> list[str]:
    return list(COMPETITION_ORDER)


def normalize_competition(competition: str) -> str:
    value = competition.strip().upper()
    if value not in COMPETITION_PROFILES:
        raise ValueError(f"Unsupported competition: {competition}")
    return value


def get_competition_profile(competition: str) -> CompetitionProfile:
    return COMPETITION_PROFILES[normalize_competition(competition)]


def list_supported_sports() -> list[str]:
    return list(SPORT_ORDER)


def normalize_sport(sport: str) -> Sport:
    value = sport.strip().lower()
    if value not in SPORT_ALERT_TYPES:
        raise ValueError(f"Unsupported sport: {sport}")
    return cast(Sport, value)


def get_sport_alert_types(sport: str) -> tuple[str, ...]:
    return SPORT_ALERT_TYPES[normalize_sport(sport)]


def get_alert_types(competition: str) -> tuple[str, ...]:
    profile = get_competition_profile(competition)
    if profile.supported_alert_types is not None:
        return profile.supported_alert_types
    return SPORT_ALERT_TYPES[profile.sport]


def get_scoreboard_url(competition: str) -> str:
    return get_competition_profile(competition).scoreboard_url


def competition_supports_odds(competition: str) -> bool:
    return get_competition_profile(competition).odds_sport_key is not None


def ensure_competition_settings(db: Session) -> None:
    existing = {
        row.competition
        for row in db.scalars(select(CompetitionSetting).where(CompetitionSetting.competition.in_(COMPETITION_ORDER))).all()
    }
    if len(existing) == len(COMPETITION_ORDER):
        return

    now = datetime.now(timezone.utc)
    for competition in COMPETITION_ORDER:
        if competition in existing:
            continue
        db.add(CompetitionSetting(competition=competition, is_enabled=True, created_at=now, updated_at=now))
    db.commit()


def list_competition_settings(db: Session) -> list[CompetitionSetting]:
    ensure_competition_settings(db)
    rows = db.scalars(select(CompetitionSetting).order_by(CompetitionSetting.competition.asc())).all()
    order = {competition: index for index, competition in enumerate(COMPETITION_ORDER)}
    return sorted(rows, key=lambda row: order.get(row.competition, len(order)))


def get_active_competitions(db: Session) -> list[str]:
    return [row.competition for row in list_competition_settings(db) if row.is_enabled]


def competition_teams_query(competition: str):
    return (
        select(Team)
        .join(CompetitionTeam, CompetitionTeam.team_id == Team.id)
        .where(CompetitionTeam.competition == competition)
    )
