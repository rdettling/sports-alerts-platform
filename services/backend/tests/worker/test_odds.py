from datetime import datetime, timezone

from app.worker import odds
from app.worker.odds import OddsOutcome, OddsSnapshot, _odds_sport_key_for_competition, game_key, select_best_for_reversed_neutral_site_game, select_best_for_single_team


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


def test_nhl_uses_regular_season_odds_feed():
    assert _odds_sport_key_for_competition("NHL") == "icehockey_nhl"
    assert game_key("Boston Bruins", "Utah Mammoth") == (
        "boston bruins",
        "utah mammoth",
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




def test_blank_api_key_disables_provider_request(monkeypatch):
    monkeypatch.setattr(odds.settings, "odds_api_key", " ")

    def unexpected(*args, **kwargs):
        raise AssertionError("must not contact provider without a key")

    monkeypatch.setattr(odds, "urlopen", unexpected)
    assert odds.fetch_odds_with_usage("NBA") == odds.OddsProviderResult({})


def test_provider_entry_point_parses_moneylines_and_usage(monkeypatch):
    import io
    import json
    from urllib.parse import parse_qs, urlparse

    payload = [{
        "home_team": "Boston Celtics",
        "away_team": "Atlanta Hawks",
        "commence_time": "2026-10-31T23:00:00Z",
        "bookmakers": [{
            "title": "Test Book",
            "last_update": "2026-10-30T12:00:00Z",
            "markets": [{"key": "h2h", "outcomes": [
                {"name": "Atlanta Hawks", "price": 125},
                {"name": "Boston Celtics", "price": -145},
            ]}],
        }],
    }]

    def response(url, timeout):
        assert urlparse(url).path == "/v4/sports/basketball_nba/odds"
        assert parse_qs(urlparse(url).query) == {
            "apiKey": ["test-odds-key"], "regions": ["us"], "markets": ["h2h"], "oddsFormat": ["american"],
        }
        assert timeout == 6
        stream = io.BytesIO(json.dumps(payload).encode())
        stream.headers = {"x-requests-used": "12", "x-requests-remaining": "488"}
        return stream

    monkeypatch.setattr(odds, "urlopen", response)
    result = odds.fetch_odds_with_usage(" nba ")
    assert (result.credits_used, result.credits_remaining) == (12, 488)
    snapshot, = result.odds_index[game_key("Boston Celtics", "Atlanta Hawks")]
    assert snapshot.bookmaker == "Test Book"
    assert snapshot.last_update == datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    assert snapshot.commence_time == datetime(2026, 10, 31, 23, tzinfo=timezone.utc)
    assert [(o.team_side, o.price_american) for o in snapshot.outcomes] == [("away", 125), ("home", -145)]
    assert odds.select_best_for_game(snapshot, datetime(2026, 11, 2, tzinfo=timezone.utc)) is None
    assert odds.select_best_for_game(snapshot, snapshot.commence_time) is snapshot
