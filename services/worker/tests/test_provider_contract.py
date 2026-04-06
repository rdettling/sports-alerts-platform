from worker.providers.balldontlie import BallDontLieProvider


def test_provider_returns_expected_shape():
    provider = BallDontLieProvider()
    schedule = provider.fetch_schedule()

    assert len(schedule) >= 1
    game = schedule[0]
    assert game.external_game_id
    assert game.home_external_team_id
    assert game.away_external_team_id
    assert game.scheduled_start_time
