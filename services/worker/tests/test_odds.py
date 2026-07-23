from worker.odds import game_key


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
