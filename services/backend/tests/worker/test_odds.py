from datetime import datetime, timezone

from app.worker import odds
from app.worker.odds import OddsOutcome, OddsSnapshot, _odds_sport_key_for_competition, closest_provider_matchups, game_key, select_best_for_reversed_neutral_site_game, select_best_for_single_team


def test_blank_api_key_disables_fetch(monkeypatch):
    monkeypatch.setattr(odds.settings, "odds_api_key", " ")
    monkeypatch.setattr(
        odds,
        "_fetch_from_provider",
        lambda _competition: (_ for _ in ()).throw(AssertionError("provider should not be called")),
    )

    assert odds.fetch_odds_index("NBA") == {}


def test_provider_failure_returns_no_odds(monkeypatch, caplog):
    monkeypatch.setattr(odds.settings, "odds_api_key", "test-key")
    monkeypatch.setattr(
        odds,
        "_fetch_from_provider",
        lambda _competition: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
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
    assert _odds_sport_key_for_competition("LA_LIGA") == "soccer_spain_la_liga"


def test_premier_competition_names_match_seeded_names():
    assert game_key("Bournemouth", "Manchester City") == game_key("AFC Bournemouth", "Manchester City")
    assert game_key("Brighton and Hove Albion", "Aston Villa") == game_key(
        "Brighton & Hove Albion", "Aston Villa"
    )
    assert _odds_sport_key_for_competition("PREMIER_LEAGUE") == "soccer_epl"


def test_champions_league_uses_its_soccer_odds_feed_and_seeded_names():
    assert _odds_sport_key_for_competition("CHAMPIONS_LEAGUE") == "soccer_uefa_champs_league"
    assert game_key("Bodø/Glimt", "Fenerbahçe") == game_key("Bodo/Glimt", "Fenerbahce")


def test_wnba_uses_its_basketball_odds_feed_and_seeded_names():
    assert _odds_sport_key_for_competition("WNBA") == "basketball_wnba"
    assert game_key("Las Vegas Aces", "New York Liberty") == ("las vegas aces", "new york liberty")
    assert game_key("Golden State Valkyries", "Toronto Tempo") == (
        "golden state valkyries",
        "toronto tempo",
    )


def test_nfl_uses_regular_season_odds_feed():
    assert _odds_sport_key_for_competition("NFL") == "americanfootball_nfl"
    assert game_key("Buffalo Bills", "Kansas City Chiefs") == (
        "buffalo bills",
        "kansas city chiefs",
    )


def test_fbs_uses_college_football_odds_feed():
    assert _odds_sport_key_for_competition("FBS") == "americanfootball_ncaaf"
    assert game_key("Alabama Crimson Tide", "Auburn Tigers") == (
        "alabama crimson tide",
        "auburn tigers",
    )


def test_fbs_name_aliases_match_odds_provider_names():
    assert game_key("App State Mountaineers", "Charlotte 49ers") == game_key(
        "Appalachian State Mountaineers", "Charlotte 49ers"
    )
    assert game_key("Connecticut Huskies", "Southern Miss Golden Eagles") == game_key(
        "UConn Huskies", "Southern Miss Golden Eagles"
    )
    assert game_key("Massachusetts Minutemen", "Stonehill Skyhawks") == game_key(
        "UMass Minutemen", "Stonehill Skyhawks"
    )
    assert game_key("Southern Miss Golden Eagles", "UConn Huskies") == game_key(
        "Southern Mississippi Golden Eagles", "UConn Huskies"
    )
    assert game_key("Sam Houston Bearkats", "Nicholls Colonels") == game_key(
        "Sam Houston State Bearkats", "Nicholls Colonels"
    )


def test_single_fbs_team_match_requires_one_provider_event():
    snapshot = OddsSnapshot(outcomes=(), bookmaker=None, last_update=None)
    odds_index = {
        game_key("UL Monroe Warhawks", "Southeastern Louisiana Lions"): [snapshot]
    }

    assert select_best_for_single_team(
        odds_index,
        ("ul monroe warhawks",),
        datetime.now(timezone.utc),
    ) is snapshot
    assert select_best_for_single_team(
        odds_index,
        ("ul monroe warhawks", "southeastern louisiana lions"),
        datetime.now(timezone.utc),
    ) is None


def test_reversed_neutral_site_odds_use_the_scoreboard_team_sides():
    snapshot = OddsSnapshot(
        outcomes=(
            OddsOutcome("virginia", "Virginia Cavaliers", 0, 120, "away"),
            OddsOutcome("west_virginia", "West Virginia Mountaineers", 1, -140, "home"),
        ),
        bookmaker="DraftKings",
        last_update=None,
    )

    selected = select_best_for_reversed_neutral_site_game(
        snapshot,
        datetime.now(timezone.utc),
        home_team_key="virginia cavaliers",
        away_team_key="west virginia mountaineers",
    )

    assert selected is not None
    assert [(outcome.outcome_label, outcome.team_side) for outcome in selected.outcomes] == [
        ("Virginia Cavaliers", "home"),
        ("West Virginia Mountaineers", "away"),
    ]


def test_closest_provider_matchups_keeps_provider_team_names():
    provider_odds = OddsSnapshot(
        outcomes=(),
        bookmaker=None,
        last_update=None,
        home_team_name="Southern Mississippi Golden Eagles",
        away_team_name="Connecticut Huskies",
    )

    assert closest_provider_matchups(
        game_key("Southern Miss Golden Eagles", "UConn Huskies"),
        {
            game_key("Southern Mississippi Golden Eagles", "Connecticut Huskies"): [
                provider_odds
            ]
        },
    ) == ("Connecticut Huskies @ Southern Mississippi Golden Eagles",)
