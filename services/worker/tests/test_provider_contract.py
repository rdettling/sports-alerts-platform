from worker.providers.balldontlie import BallDontLieProvider


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

    provider = BallDontLieProvider(fetch_json=lambda _: payload)
    schedule = provider.fetch_schedule()

    assert len(schedule) == 1
    game = schedule[0]
    assert game.external_game_id == "401705001"
    assert game.home_external_team_id == "1610612747"
    assert game.away_external_team_id == "1610612738"
    assert game.status == "in_progress"
    assert game.home_score == 102
    assert game.away_score == 98
