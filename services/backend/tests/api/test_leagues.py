from sqlalchemy import func, select

from app.db.models import Team
from app.db.session import SessionLocal
from app.services.leagues import get_alert_types, get_league_profile, list_supported_leagues


def test_league_profiles_are_the_single_source_of_sport_and_provider_configuration():
    assert list_supported_leagues() == ["NBA", "WNBA", "NFL", "MLB", "MLS", "WORLD_CUP"]

    nba = get_league_profile("NBA")
    assert (nba.sport, nba.live_sync_interval_seconds, nba.odds_sport_key) == (
        "basketball",
        120,
        "basketball_nba",
    )

    wnba = get_league_profile("WNBA")
    assert (wnba.sport, wnba.live_sync_interval_seconds, wnba.odds_sport_key) == (
        "basketball",
        120,
        "basketball_wnba",
    )
    assert wnba.scoreboard_url.endswith("/sports/basketball/wnba/scoreboard")
    assert get_alert_types("WNBA") == get_alert_types("NBA")
    assert get_alert_types("NBA") == ("game_start", "close_game_late", "overtime_start", "final_result")

    nfl = get_league_profile("NFL")
    assert (nfl.sport, nfl.live_sync_interval_seconds, nfl.odds_sport_key) == (
        "football",
        120,
        "americanfootball_nfl",
    )
    assert nfl.scoreboard_url.endswith("/sports/football/nfl/scoreboard")
    assert get_alert_types("NFL") == ("game_start", "close_game_late", "overtime_start", "final_result")

    mlb = get_league_profile("MLB")
    assert (mlb.sport, mlb.live_sync_interval_seconds, mlb.odds_sport_key) == (
        "baseball",
        300,
        "baseball_mlb",
    )
    assert get_alert_types("MLB") == ("game_start", "inning_start", "extra_innings_start", "final_result")

    mls = get_league_profile("MLS")
    assert (mls.sport, mls.live_sync_interval_seconds, mls.odds_sport_key) == (
        "soccer",
        180,
        "soccer_usa_mls",
    )
    assert mls.scoreboard_url.endswith("/sports/soccer/usa.1/scoreboard")

    world_cup = get_league_profile("WORLD_CUP")
    assert (world_cup.sport, world_cup.live_sync_interval_seconds, world_cup.odds_sport_key) == (
        "soccer",
        180,
        "soccer_fifa_world_cup",
    )
    assert get_alert_types("MLS") == get_alert_types("WORLD_CUP")
    assert "overtime_start" not in get_alert_types("MLB")
    assert "overtime_start" not in get_alert_types("MLS")
    assert "extra_innings_start" not in get_alert_types("NBA")
    assert "extra_innings_start" not in get_alert_types("MLS")


def test_public_leagues_include_sport_and_live_cadence(client):
    response = client.get("/leagues")

    assert response.status_code == 200
    assert [
        (
            item["league"],
            item["sport"],
            item["live_sync_interval_seconds"],
        )
        for item in response.json()
    ] == [
        ("NBA", "basketball", 120),
        ("WNBA", "basketball", 120),
        ("NFL", "football", 120),
        ("MLB", "baseball", 300),
        ("MLS", "soccer", 180),
        ("WORLD_CUP", "soccer", 180),
    ]


def test_mls_team_catalog_contains_all_current_clubs(client):
    client.get("/leagues")
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Team).where(Team.league == "MLS"))
        abbreviations = set(db.scalars(select(Team.abbreviation).where(Team.league == "MLS")))

    assert count == 30
    assert {"LA", "LAFC", "MIA", "RBNY", "SD"} <= abbreviations


def test_wnba_team_catalog_contains_all_current_clubs(client):
    client.get("/leagues")
    with SessionLocal() as db:
        teams = db.scalars(select(Team).where(Team.league == "WNBA")).all()

    assert len(teams) == 15
    assert {
        (team.external_team_id, team.abbreviation)
        for team in teams
    } >= {
        ("129689", "GS"),
        ("132052", "POR"),
        ("131935", "TOR"),
    }


def test_nfl_team_catalog_contains_all_teams(client):
    client.get("/leagues")
    with SessionLocal() as db:
        teams = db.scalars(select(Team).where(Team.league == "NFL")).all()

    assert len(teams) == 32
    assert {
        (team.external_team_id, team.abbreviation)
        for team in teams
    } >= {
        ("2", "BUF"),
        ("12", "KC"),
        ("34", "HOU"),
        ("33", "BAL"),
    }
