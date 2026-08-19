from app.worker.odds import _odds_sport_key_for_league, game_key


def test_world_cup_name_aliases_match_seeded_names():
    assert game_key("Canada", "Bosnia & Herzegovina") == game_key("Canada", "Bosnia-Herzegovina")
    assert game_key("USA", "Paraguay") == game_key("United States", "Paraguay")
    assert game_key("DR Congo", "Japan") == game_key("Congo DR", "Japan")
    assert game_key("Turkey", "Mexico") == game_key("Turkiye", "Mexico")
    assert game_key("Curaçao", "Germany") == game_key("Curacao", "Germany")
    assert game_key("Czech Republic", "Egypt") == game_key("Czechia", "Egypt")


def test_mls_name_aliases_match_seeded_names():
    assert game_key("Los Angeles FC", "LA Galaxy") == game_key("LAFC", "LA Galaxy")
    assert game_key("Columbus Crew SC", "Houston Dynamo") == game_key("Columbus Crew", "Houston Dynamo FC")
    assert game_key("New York Red Bulls", "Chicago Fire") == game_key("Red Bull New York", "Chicago Fire FC")
    assert game_key("Vancouver Whitecaps FC", "San Diego FC") == game_key("Vancouver Whitecaps", "San Diego FC")


def test_wnba_uses_its_basketball_odds_feed_and_seeded_names():
    assert _odds_sport_key_for_league("WNBA") == "basketball_wnba"
    assert game_key("Las Vegas Aces", "New York Liberty") == ("las vegas aces", "new york liberty")
    assert game_key("Golden State Valkyries", "Toronto Tempo") == (
        "golden state valkyries",
        "toronto tempo",
    )


def test_nfl_uses_regular_season_odds_feed():
    assert _odds_sport_key_for_league("NFL") == "americanfootball_nfl"
    assert game_key("Buffalo Bills", "Kansas City Chiefs") == (
        "buffalo bills",
        "kansas city chiefs",
    )
