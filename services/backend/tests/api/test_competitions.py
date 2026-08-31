from app.db.models import CompetitionSetting
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query
from app.services.competitions import (
    ensure_competition_settings,
    get_alert_types,
    get_competition_profile,
    list_supported_competitions,
)


def test_fresh_database_activates_the_supported_catalog():
    with SessionLocal() as db:
        ensure_competition_settings(db)
        settings = db.query(CompetitionSetting).all()

    assert len(settings) == len(list_supported_competitions())
    assert all(setting.is_enabled for setting in settings)


def test_new_profiles_start_inactive_without_changing_existing_values():
    with SessionLocal() as db:
        db.add_all(
            [
                CompetitionSetting(competition="NBA", is_enabled=True),
                CompetitionSetting(competition="WNBA", is_enabled=False),
            ]
        )
        db.commit()

        ensure_competition_settings(db)
        settings = {
            setting.competition: setting.is_enabled
            for setting in db.query(CompetitionSetting).all()
        }

    assert settings["NBA"] is True
    assert settings["WNBA"] is False
    assert all(
        settings[competition] is False
        for competition in list_supported_competitions()
        if competition not in {"NBA", "WNBA"}
    )


def test_competition_profiles_are_the_single_source_of_sport_and_provider_configuration():
    assert list_supported_competitions() == [
        "NBA",
        "WNBA",
        "NFL",
        "FBS",
        "MLB",
        "MLS",
        "LA_LIGA",
        "PREMIER_LEAGUE",
        "WORLD_CUP",
    ]

    nba = get_competition_profile("NBA")
    assert (nba.sport, nba.live_sync_interval_seconds, nba.odds_sport_key) == (
        "basketball",
        120,
        "basketball_nba",
    )

    wnba = get_competition_profile("WNBA")
    assert (wnba.sport, wnba.live_sync_interval_seconds, wnba.odds_sport_key) == (
        "basketball",
        120,
        "basketball_wnba",
    )
    assert wnba.scoreboard_url.endswith("/sports/basketball/wnba/scoreboard")
    assert get_alert_types("WNBA") == get_alert_types("NBA")
    assert get_alert_types("NBA") == ("game_start", "close_game_late", "overtime_start", "final_result")

    nfl = get_competition_profile("NFL")
    assert (nfl.sport, nfl.live_sync_interval_seconds, nfl.odds_sport_key) == (
        "football",
        120,
        "americanfootball_nfl",
    )
    assert nfl.scoreboard_url.endswith("/sports/football/nfl/scoreboard")
    assert get_alert_types("NFL") == ("game_start", "close_game_late", "overtime_start", "final_result")

    fbs = get_competition_profile("FBS")
    assert (fbs.sport, fbs.live_sync_interval_seconds, fbs.odds_sport_key) == (
        "football",
        120,
        "americanfootball_ncaaf",
    )
    assert fbs.scoreboard_url.endswith("/sports/football/college-football/scoreboard")
    assert dict(fbs.scoreboard_params) == {"groups": "80"}
    assert get_alert_types("FBS") == get_alert_types("NFL")

    mlb = get_competition_profile("MLB")
    assert (mlb.sport, mlb.live_sync_interval_seconds, mlb.odds_sport_key) == (
        "baseball",
        300,
        "baseball_mlb",
    )
    assert get_alert_types("MLB") == ("game_start", "inning_start", "extra_innings_start", "final_result")

    mls = get_competition_profile("MLS")
    assert (mls.sport, mls.live_sync_interval_seconds, mls.odds_sport_key) == (
        "soccer",
        180,
        "soccer_usa_mls",
    )
    assert mls.scoreboard_url.endswith("/sports/soccer/usa.1/scoreboard")

    la_liga = get_competition_profile("LA_LIGA")
    assert (la_liga.sport, la_liga.live_sync_interval_seconds, la_liga.odds_sport_key) == (
        "soccer",
        180,
        "soccer_spain_la_liga",
    )
    assert la_liga.scoreboard_url.endswith("/sports/soccer/esp.1/scoreboard")
    assert get_alert_types("LA_LIGA") == (
        "game_start",
        "second_half_start",
        "score_changed",
        "final_result",
    )

    premier_competition = get_competition_profile("PREMIER_LEAGUE")
    assert (
        premier_competition.sport,
        premier_competition.live_sync_interval_seconds,
        premier_competition.odds_sport_key,
    ) == ("soccer", 180, "soccer_epl")
    assert premier_competition.scoreboard_url.endswith("/sports/soccer/eng.1/scoreboard")
    assert get_alert_types("PREMIER_LEAGUE") == get_alert_types("LA_LIGA")

    world_cup = get_competition_profile("WORLD_CUP")
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


def test_public_competitions_include_sport_and_live_cadence(client):
    response = client.get("/competitions")

    assert response.status_code == 200
    la_liga = next(item for item in response.json() if item["competition"] == "LA_LIGA")
    assert la_liga["is_enabled"] is True
    assert la_liga["label"] == "La Liga"
    assert la_liga["badge_label"] == "LALIGA"
    premier_competition = next(item for item in response.json() if item["competition"] == "PREMIER_LEAGUE")
    assert premier_competition["is_enabled"] is True
    assert premier_competition["label"] == "Premier League"
    assert premier_competition["badge_label"] == "EPL"
    assert [
        (
            item["competition"],
            item["sport"],
            item["live_sync_interval_seconds"],
        )
        for item in response.json()
    ] == [
        ("NBA", "basketball", 120),
        ("WNBA", "basketball", 120),
        ("NFL", "football", 120),
        ("FBS", "football", 120),
        ("MLB", "baseball", 300),
        ("MLS", "soccer", 180),
        ("LA_LIGA", "soccer", 180),
        ("PREMIER_LEAGUE", "soccer", 180),
        ("WORLD_CUP", "soccer", 180),
    ]


def test_public_competitions_exclude_inactive_entries(client):
    with SessionLocal() as db:
        setting = db.get(CompetitionSetting, "MLB")
        assert setting is not None
        setting.is_enabled = False
        db.commit()

    competitions = client.get("/competitions").json()

    assert "MLB" not in {item["competition"] for item in competitions}


def test_mls_team_catalog_contains_all_current_clubs(client):
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("MLS")).all()

    assert len(teams) == 30
    assert {"LA", "LAFC", "MIA", "RBNY", "SD"} <= {team.abbreviation for team in teams}


def test_fbs_team_catalog_contains_all_current_programs(client):
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("FBS")).all()

    assert len(teams) == 138
    assert {"ALA", "NDSU", "ND", "OSU", "SAC", "UGA"} <= {
        team.abbreviation for team in teams
    }


def test_la_liga_team_catalog_contains_all_current_clubs(client):
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("LA_LIGA")).all()

    assert len(teams) == 20
    assert {(team.external_team_id, team.abbreviation) for team in teams} >= {
        ("83", "BAR"),
        ("86", "RMA"),
        ("87", "RAC"),
        ("90", "DEP"),
        ("99", "MCF"),
        ("1068", "ATM"),
    }


def test_premier_competition_team_catalog_contains_all_current_clubs(client):
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("PREMIER_LEAGUE")).all()

    assert len(teams) == 20
    assert {(team.external_team_id, team.abbreviation) for team in teams} >= {
        ("306", "HUL"),
        ("359", "ARS"),
        ("360", "MAN"),
        ("364", "LIV"),
        ("382", "MNC"),
        ("388", "COV"),
    }


def test_wnba_team_catalog_contains_all_current_clubs(client):
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("WNBA")).all()

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
    client.get("/competitions")
    with SessionLocal() as db:
        teams = db.scalars(competition_teams_query("NFL")).all()

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
