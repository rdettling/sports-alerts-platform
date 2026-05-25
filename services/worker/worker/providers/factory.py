from worker.config import settings
from worker.providers.balldontlie import BallDontLieProvider
from worker.providers.base import SportsProvider


def get_provider() -> SportsProvider:
    if settings.nba_provider in {"balldontlie", "espn"}:
        return BallDontLieProvider()
    raise ValueError(f"Unsupported nba provider: {settings.nba_provider}")
