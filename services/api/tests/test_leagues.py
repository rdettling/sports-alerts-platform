from app.services.leagues import get_league_profile, list_supported_leagues


def test_league_profiles_are_the_single_source_of_sport_and_provider_configuration():
    assert list_supported_leagues() == ["NBA", "MLB", "WORLD_CUP"]

    nba = get_league_profile("NBA")
    assert (nba.sport, nba.live_sync_interval_seconds, nba.odds_sport_key) == (
        "basketball",
        120,
        "basketball_nba",
    )

    mlb = get_league_profile("MLB")
    assert (mlb.sport, mlb.live_sync_interval_seconds, mlb.odds_sport_key) == (
        "baseball",
        300,
        "baseball_mlb",
    )

    world_cup = get_league_profile("WORLD_CUP")
    assert (world_cup.sport, world_cup.live_sync_interval_seconds, world_cup.odds_sport_key) == (
        "soccer",
        180,
        "soccer_fifa_world_cup",
    )


def test_public_leagues_include_sport_and_live_cadence(client):
    response = client.get("/leagues")

    assert response.status_code == 200
    assert [
        (item["league"], item["sport"], item["live_sync_interval_seconds"])
        for item in response.json()
    ] == [
        ("NBA", "basketball", 120),
        ("MLB", "baseball", 300),
        ("WORLD_CUP", "soccer", 180),
    ]
