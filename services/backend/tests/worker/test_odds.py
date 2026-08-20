from app.worker import odds
from app.worker.odds import _odds_sport_key_for_league, game_key


def test_blank_api_key_disables_fetch(monkeypatch):
    monkeypatch.setattr(odds.settings, "odds_api_key", " ")
    monkeypatch.setattr(
        odds,
        "_fetch_from_provider",
        lambda _league: (_ for _ in ()).throw(AssertionError("provider should not be called")),
    )

    assert odds.fetch_odds_index("NBA") == {}


def test_provider_failure_returns_no_odds(monkeypatch, caplog):
    monkeypatch.setattr(odds.settings, "odds_api_key", "test-key")
    monkeypatch.setattr(
        odds,
        "_fetch_from_provider",
        lambda _league: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    with caplog.at_level("WARNING", logger="app.worker.odds"):
        assert odds.fetch_odds_index("NBA") == {}

    assert "Odds API request failed: provider unavailable" in caplog.text


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


def test_la_liga_name_aliases_match_seeded_names():
    assert game_key("Athletic Bilbao", "Sevilla") == game_key("Athletic Club", "Sevilla")
    assert game_key("Real Racing Club de Santander", "Getafe") == game_key("Racing Santander", "Getafe")
    assert game_key("Elche CF", "Barcelona") == game_key("Elche", "Barcelona")
    assert game_key("CA Osasuna", "Levante") == game_key("Osasuna", "Levante")
    assert game_key("Deportivo La Coruña", "Málaga") == game_key("Deportivo", "Málaga")
    assert _odds_sport_key_for_league("LA_LIGA") == "soccer_spain_la_liga"


def test_premier_league_names_match_seeded_names():
    assert game_key("Bournemouth", "Manchester City") == game_key("AFC Bournemouth", "Manchester City")
    assert game_key("Brighton and Hove Albion", "Aston Villa") == game_key(
        "Brighton & Hove Albion", "Aston Villa"
    )
    assert _odds_sport_key_for_league("PREMIER_LEAGUE") == "soccer_epl"


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
