from datetime import datetime, timezone

from worker.providers.base import NbaProvider, ProviderGame


class BallDontLieProvider(NbaProvider):
    def fetch_schedule(self) -> list[ProviderGame]:
        return [
            ProviderGame(
                external_game_id="placeholder-game",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
        ]

    def fetch_game_updates(self, external_game_ids: list[str]) -> list[ProviderGame]:
        if not external_game_ids:
            return []
        return [
            ProviderGame(
                external_game_id=external_game_id,
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
            for external_game_id in external_game_ids
        ]
