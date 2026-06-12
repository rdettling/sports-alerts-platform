from worker.config import settings
from worker.providers.espn import EspnScoreboardProvider
from worker.providers.base import SportsProvider


def get_provider() -> SportsProvider:
    if settings.scoreboard_provider == "espn":
        return EspnScoreboardProvider()
    raise ValueError(f"Unsupported scoreboard provider: {settings.scoreboard_provider}")
