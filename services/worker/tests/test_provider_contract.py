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
                            {"homeAway": "home", "score": "102", "team": {"id": "13", "abbreviation": "LAL"}},
                            {"homeAway": "away", "score": "98", "team": {"id": "2", "abbreviation": "BOS"}},
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
    assert game.home_external_team_id == "13"
    assert game.away_external_team_id == "2"
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
                            {"homeAway": "home", "score": "3", "team": {"id": "14", "abbreviation": "TOR"}},
                            {"homeAway": "away", "score": "2", "team": {"id": "28", "abbreviation": "MIA"}},
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


def test_provider_uses_numeric_team_ids_for_mlb():
    payload = {
        "events": [
            {
                "id": "401815999",
                "date": "2026-05-28T22:10:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 1,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "4", "abbreviation": "CHW"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "11", "abbreviation": "ATH"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = BallDontLieProvider(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLB", [ScoreboardRequest(date="20260528")])
    assert len(schedule) == 1
    assert schedule[0].home_external_team_id == "4"
    assert schedule[0].away_external_team_id == "11"


def test_provider_skips_events_with_invalid_placeholder_team_ids():
    payload = {
        "events": [
            {
                "id": "401859963",
                "date": "2026-05-28T23:10:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "-1", "abbreviation": "TBD"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "18", "abbreviation": "NY"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = BallDontLieProvider(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", [ScoreboardRequest(date="20260528")])
    assert schedule == []
