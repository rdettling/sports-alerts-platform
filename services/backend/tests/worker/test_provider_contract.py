from app.worker.scoreboard import EspnScoreboardClient


def test_provider_failure_logs_compact_request_context(caplog):
    def fail_fetch(_competition, _params):
        raise RuntimeError("provider unavailable")

    games = EspnScoreboardClient(fetch_json=fail_fetch).fetch_games("NBA", ["20260406"])

    assert games == []
    assert "ESPN request failed competition=NBA date=20260406 error=provider unavailable" in caplog.text


def test_fbs_provider_requests_the_complete_fbs_group():
    requests = []

    def record_fetch(competition, params):
        requests.append((competition, params))
        return {"events": []}

    EspnScoreboardClient(fetch_json=record_fetch).fetch_games("FBS", ["20260829"])

    assert requests == [
        ("FBS", {"groups": "80", "limit": "1000", "dates": "20260829"})
    ]


def test_provider_parses_espn_payload_shape():
    payload = {
        "events": [
            {
                "id": "401705001",
                "date": "2026-04-06T02:00Z",
                "competitions": [
                    {
                        "broadcasts": [
                            {"market": "national", "names": [" ESPN ", "espn", None, 12]},
                            {"market": "home", "names": "not-a-list"},
                            "not-an-object",
                        ],
                        "geoBroadcasts": [
                            {"media": {"shortName": "ABC"}},
                            {"media": {"shortName": " ESPN "}},
                            {"media": None},
                            "not-an-object",
                        ],
                        "status": {
                            "period": 4,
                            "displayClock": "02:13",
                            "type": {"state": "in", "name": "STATUS_IN_PROGRESS", "completed": False},
                        },
                        "competitors": [
                            {
                                "homeAway": "home",
                                "score": "102",
                                "team": {"id": "13", "abbreviation": "LAL"},
                                "records": [
                                    {"type": "home", "summary": "27-13"},
                                    {"type": "total", "summary": "48-31"},
                                ],
                            },
                            {
                                "homeAway": "away",
                                "score": "98",
                                "team": {"id": "2", "abbreviation": "BOS"},
                                "records": [
                                    {"type": "total", "summary": "57-22"},
                                    {"type": "road", "summary": "27-12"},
                                ],
                            },
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
    assert game.home_team_record == "48-31"
    assert game.away_team_record == "57-22"
    assert game.broadcast_names == ["ESPN", "ABC"]
    assert game.context_label is None


def test_provider_parses_soccer_record_and_allows_missing_record():
    payload = {
        "events": [
            {
                "id": "757653",
                "date": "2026-09-16T19:00Z",
                "competitions": [
                    {
                        "status": {
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}
                        },
                        "competitors": [
                            {
                                "homeAway": "home",
                                "score": "0",
                                "team": {"id": "359", "abbreviation": "ARS"},
                                "records": [{"type": "total", "summary": "4-2-1"}],
                            },
                            {
                                "homeAway": "away",
                                "score": "0",
                                "team": {"id": "364", "abbreviation": "LIV"},
                                "records": None,
                            },
                        ],
                    }
                ],
            }
        ]
    }

    game = EspnScoreboardClient(fetch_json=lambda _, __: payload).fetch_games(
        "PREMIER_LEAGUE", ["20260916"]
    )[0]

    assert game.home_team_record == "4-2-1"
    assert game.away_team_record is None
    assert game.broadcast_names == []


def test_soccer_competition_feeds_preserve_shared_club_ids():
    def payload(game_id: str) -> dict:
        return {
            "events": [
                {
                    "id": game_id,
                    "date": "2026-09-01T19:00Z",
                    "competitions": [
                        {
                            "status": {
                                "period": 0,
                                "displayClock": "0:00",
                                "type": {
                                    "state": "pre",
                                    "name": "STATUS_SCHEDULED",
                                    "completed": False,
                                },
                            },
                            "competitors": [
                                {
                                    "homeAway": "home",
                                    "score": "0",
                                    "team": {"id": "359", "abbreviation": "ARS"},
                                },
                                {
                                    "homeAway": "away",
                                    "score": "0",
                                    "team": {"id": "364", "abbreviation": "LIV"},
                                },
                            ],
                        }
                    ],
                }
            ]
        }

    provider = EspnScoreboardClient(
        fetch_json=lambda competition, _: payload(f"{competition.lower()}-game")
    )
    premier_game = provider.fetch_games("PREMIER_LEAGUE", ["20260901"])[0]
    la_liga_game = provider.fetch_games("LA_LIGA", ["20260901"])[0]

    assert premier_game.home_external_team_id == la_liga_game.home_external_team_id == "359"
    assert premier_game.away_external_team_id == la_liga_game.away_external_team_id == "364"


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


def test_provider_parses_nfl_preseason_state_and_context():
    payload = {
        "events": [
            {
                "id": "401873272",
                "date": "2026-08-13T23:00Z",
                "season": {"year": 2026, "type": 1, "slug": "preseason"},
                "week": {"number": 2},
                "competitions": [
                    {
                        "notes": [],
                        "status": {
                            "period": 2,
                            "displayClock": "9:35",
                            "type": {
                                "state": "in",
                                "name": "STATUS_IN_PROGRESS",
                                "completed": False,
                            },
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "10", "team": {"id": "4", "abbreviation": "CIN"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "8", "abbreviation": "DET"}},
                        ],
                    }
                ],
            }
        ]
    }

    schedule = EspnScoreboardClient(fetch_json=lambda _, __: payload).fetch_games("NFL", ["20260813"])

    assert len(schedule) == 1
    game = schedule[0]
    assert (game.home_external_team_id, game.away_external_team_id) == ("4", "8")
    assert (game.status, game.period, game.clock, game.home_score, game.away_score) == (
        "in_progress",
        2,
        "9:35",
        10,
        0,
    )
    assert (game.season_slug, game.season_week, game.context_label) == (
        "preseason",
        2,
        "Preseason · Week 2",
    )


def test_provider_uses_meaningful_nfl_context_and_leaves_standard_games_unlabeled():
    payload = {
        "events": [
            {
                "id": "401999201",
                "date": "2026-09-10T20:00Z",
                "season": {"year": 2026, "type": 2, "slug": "regular-season"},
                "week": {"number": 1},
                "competitions": [
                    {
                        "notes": [],
                        "status": {
                            "period": 0,
                            "displayClock": "0:00",
                            "type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0", "team": {"id": "2", "abbreviation": "BUF"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "12", "abbreviation": "KC"}},
                        ],
                    }
                ],
            },
            {
                "id": "401999202",
                "date": "2027-01-17T20:00Z",
                "season": {"year": 2026, "type": 3, "slug": "post-season"},
                "week": {"number": 1},
                "competitions": [
                    {
                        "notes": [{"headline": "Wild Card Playoffs"}],
                        "status": {
                            "period": 4,
                            "displayClock": "0:00",
                            "type": {"state": "post", "name": "STATUS_FINAL", "completed": True},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "24", "team": {"id": "2", "abbreviation": "BUF"}},
                            {"homeAway": "away", "score": "21", "team": {"id": "12", "abbreviation": "KC"}},
                        ],
                    }
                ],
            },
        ]
    }

    schedule = EspnScoreboardClient(fetch_json=lambda _, __: payload).fetch_games("NFL", ["20260910"])

    regular = next(game for game in schedule if game.external_game_id == "401999201")
    postseason = next(game for game in schedule if game.external_game_id == "401999202")
    assert regular.context_label is None
    assert (regular.season_slug, regular.season_week) == ("regular-season", 1)
    assert postseason.context_label == "Wild Card Playoffs"
    assert postseason.is_final is True


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
