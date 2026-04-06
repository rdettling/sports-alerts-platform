from worker.config import settings
from worker.providers.balldontlie import BallDontLieProvider
from worker.providers.base import NbaProvider


def get_provider() -> NbaProvider:
    if settings.nba_provider == "balldontlie":
        return BallDontLieProvider()
    raise ValueError(f"Unsupported nba provider: {settings.nba_provider}")
