from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class EspnRequest:
    date: str


@dataclass
class ProviderGame:
    external_game_id: str
    home_external_team_id: str
    away_external_team_id: str
    scheduled_start_time: datetime
    status: str
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    clock: str | None = None
    is_final: bool = False


class NbaProvider(Protocol):
    def fetch_games(self, requests: list[EspnRequest]) -> list[ProviderGame]: ...

    def expected_call_count(self, requests: list[EspnRequest]) -> int: ...
