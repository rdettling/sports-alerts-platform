from worker.scoreboard import EspnScoreboardClient


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

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", ["20260406"])

    assert len(schedule) == 1
    game = schedule[0]
    assert game.external_game_id == "401705001"
    assert game.home_external_team_id == "13"
    assert game.away_external_team_id == "2"
    assert game.status == "in_progress"
    assert game.home_score == 102
    assert game.away_score == 98
    assert game.context_label is None


def test_provider_builds_nba_context_label_from_round_and_series():
    payload = {
        "events": [
            {
                "id": "401999001",
                "date": "2026-06-14T00:30Z",
                "season": {"year": 2026, "type": 3, "slug": "post-season"},
                "competitions": [
                    {
                        "notes": [{"headline": "NBA Finals - Game 5"}],
                        "series": {"summary": "NY leads series 3-1"},
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "24", "abbreviation": "SA"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "18", "abbreviation": "NY"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", ["20260613"])
    assert len(schedule) == 1
    assert schedule[0].context_label == "NBA Finals - Game 5 · NY leads series 3-1"


def test_provider_parses_wnba_state_team_ids_and_postseason_context():
    payload = {
        "events": [
            {
                "id": "401999101",
                "date": "2026-09-20T19:00Z",
                "competitions": [
                    {
                        "notes": [{"headline": "WNBA Semifinals - Game 3"}],
                        "series": {"summary": "NY leads series 2-0"},
                        "status": {
                            "period": 4,
                            "displayClock": "01:12",
                            "type": {"state": "in", "name": "STATUS_IN_PROGRESS", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "82", "team": {"id": "9", "abbreviation": "NY"}},
                            {"homeAway": "away", "score": "79", "team": {"id": "17", "abbreviation": "LV"}},
                        ],
                    }
                ],
            },
            {
                "id": "401999102",
                "date": "2026-09-18T19:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 4,
                            "displayClock": "0:00",
                            "type": {"state": "post", "name": "STATUS_FINAL", "completed": True},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "88", "team": {"id": "9", "abbreviation": "NY"}},
                            {"homeAway": "away", "score": "80", "team": {"id": "17", "abbreviation": "LV"}},
                        ],
                    }
                ],
            },
        ]
    }

    schedule = EspnScoreboardClient(fetch_json=lambda _, __: payload).fetch_games("WNBA", ["20260920"])

    assert len(schedule) == 2
    live = next(game for game in schedule if game.external_game_id == "401999101")
    final = next(game for game in schedule if game.external_game_id == "401999102")
    assert (live.home_external_team_id, live.away_external_team_id) == ("9", "17")
    assert (live.status, live.period, live.clock, live.home_score, live.away_score) == (
        "in_progress",
        4,
        "01:12",
        82,
        79,
    )
    assert live.context_label == "WNBA Semifinals - Game 3 · NY leads series 2-0"
    assert final.status == "final"
    assert final.is_final is True


def test_provider_builds_world_cup_stage_context_label():
    payload = {
        "events": [
            {
                "id": "760416",
                "date": "2026-06-12T19:00Z",
                "season": {"year": 2026, "type": 13802, "slug": "group-stage"},
                "competitions": [
                    {
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "660", "abbreviation": "USA"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "203", "abbreviation": "MEX"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("WORLD_CUP", ["20260612"])
    assert len(schedule) == 1
    assert schedule[0].context_label == "Group Stage"


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

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", ["20260525"])

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

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLB", ["20260527"])
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

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLB", ["20260528"])
    assert len(schedule) == 1
    assert schedule[0].home_external_team_id == "4"
    assert schedule[0].away_external_team_id == "11"


def test_provider_parses_mls_soccer_clock_and_team_ids():
    payload = {
        "events": [
            {
                "id": "401999100",
                "date": "2026-03-15T02:30:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 2,
                            "displayClock": "67:12",
                            "type": {
                                "state": "in",
                                "name": "STATUS_IN_PROGRESS",
                                "completed": False,
                                "shortDetail": "68'",
                            },
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "1", "team": {"id": "187", "abbreviation": "LA"}},
                            {"homeAway": "away", "score": "2", "team": {"id": "18966", "abbreviation": "LAFC"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLS", ["20260314"])

    assert len(schedule) == 1
    assert schedule[0].home_external_team_id == "187"
    assert schedule[0].away_external_team_id == "18966"
    assert schedule[0].clock == "68'"
    assert schedule[0].context_label is None


def test_provider_maps_status_postponed_payload_to_postponed():
    payload = {
        "events": [
            {
                "id": "401815716",
                "date": "2026-06-11T23:40:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {
                                "state": "post",
                                "name": "STATUS_POSTPONED",
                                "completed": False,
                                "description": "Postponed",
                                "shortDetail": "Postponed",
                            },
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "4", "abbreviation": "CHW"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "15", "abbreviation": "ATL"}},
                        ],
                    }
                ],
            }
        ]
    }

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("MLB", ["20260611"])
    assert len(schedule) == 1
    assert schedule[0].status == "postponed"
    assert schedule[0].is_final is False


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

    provider = EspnScoreboardClient(fetch_json=lambda _, __: payload)
    schedule = provider.fetch_games("NBA", ["20260528"])
    assert schedule == []
