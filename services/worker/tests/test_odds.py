from worker.odds import game_key


def test_world_cup_name_aliases_match_seeded_names():
    assert game_key("Canada", "Bosnia & Herzegovina") == game_key("Canada", "Bosnia-Herzegovina")
    assert game_key("USA", "Paraguay") == game_key("United States", "Paraguay")
    assert game_key("DR Congo", "Japan") == game_key("Congo DR", "Japan")
    assert game_key("Turkey", "Mexico") == game_key("Turkiye", "Mexico")
    assert game_key("Curaçao", "Germany") == game_key("Curacao", "Germany")
    assert game_key("Czech Republic", "Egypt") == game_key("Czechia", "Egypt")
