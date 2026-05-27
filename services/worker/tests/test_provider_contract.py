from worker.providers.balldontlie import BallDontLieProvider
from worker.providers.base import ScoreboardRequest


def test_provider_parses_espn_payload_shape():
    payload = {
        "events": [
            {
                "id": "401705001",
                "date": "2026-04-06T02:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 4,
                            "displayClock": "02:13",
                            "type": {"state": "in", "name": "STATUS_IN_PROGRESS", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "102", "team": {"abbreviation": "LAL"}},
                            {"homeAway": "away", "score": "98", "team": {"abbreviation": "BOS"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = BallDontLieProvider(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", [ScoreboardRequest(date="20260406")])

    assert len(schedule) == 1
    game = schedule[0]
    assert game.external_game_id == "401705001"
    assert game.home_external_team_id == "1610612747"
    assert game.away_external_team_id == "1610612738"
    assert game.status == "in_progress"
    assert game.home_score == 102
    assert game.away_score == 98


def test_provider_skips_if_necessary_playoff_games():
    payload = {
        "events": [
            {
                "id": "401705999",
                "date": "2026-05-25T00:00Z",
                "competitions": [
                    {
                        "notes": [{"headline": "West Finals - Game 7 If Necessary"}],
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"abbreviation": "OKC"}},
                            {"homeAway": "away", "score": "0", "team": {"abbreviation": "MIN"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = BallDontLieProvider(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", [ScoreboardRequest(date="20260525")])

    assert schedule == []


def test_provider_uses_mlb_short_detail_for_half_inning_clock():
    payload = {
        "events": [
            {
                "id": "401815518",
                "date": "2026-05-27T17:07:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 6,
                            "displayClock": "0:00",
                            "type": {
                                "state": "in",
                                "name": "STATUS_IN_PROGRESS",
                                "completed": False,
                                "shortDetail": "Top 6th",
                            },
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "3", "team": {"abbreviation": "TOR"}},
                            {"homeAway": "away", "score": "2", "team": {"abbreviation": "MIA"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = BallDontLieProvider(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLB", [ScoreboardRequest(date="20260527")])
    assert len(schedule) == 1
    assert schedule[0].clock == "Top 6th"
