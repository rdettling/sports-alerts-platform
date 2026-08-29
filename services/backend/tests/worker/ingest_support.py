from datetime import datetime, timedelta, timezone

from app.worker.odds import OddsOutcome, OddsSnapshot
from app.worker.scoreboard import ScoreboardGame


def make_snapshot(
    *,
    away_label: str,
    away_price: int | None,
    home_label: str,
    home_price: int | None,
    bookmaker: str = "DraftKings",
    last_update: datetime | None = None,
    commence_time: datetime | None = None,
    draw_price: int | None = None,
) -> OddsSnapshot:
    outcomes = [
        OddsOutcome(outcome_key=away_label.lower().replace(" ", "_"), outcome_label=away_label, outcome_order=0, price_american=away_price, team_side="away"),
        OddsOutcome(outcome_key=home_label.lower().replace(" ", "_"), outcome_label=home_label, outcome_order=1 if draw_price is None else 2, price_american=home_price, team_side="home"),
    ]
    if draw_price is not None:
        outcomes.insert(1, OddsOutcome(outcome_key="draw", outcome_label="Draw", outcome_order=1, price_american=draw_price, team_side=None))
    return OddsSnapshot(
        outcomes=tuple(outcomes),
        bookmaker=bookmaker,
        last_update=last_update,
        commence_time=commence_time,
    )


def make_game(
    *,
    external_game_id: str,
    home_external_team_id: str,
    away_external_team_id: str,
    home_team_name: str | None = None,
    home_team_abbreviation: str | None = None,
    away_team_name: str | None = None,
    away_team_abbreviation: str | None = None,
    status: str,
    scheduled_start_time: datetime | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    period: int | None = None,
    clock: str | None = None,
    is_final: bool = False,
    context_label: str | None = None,
    home_team_record: str | None = None,
    away_team_record: str | None = None,
    season_slug: str | None = None,
    season_week: int | None = None,
) -> ScoreboardGame:
    return ScoreboardGame(
        external_game_id=external_game_id,
        home_external_team_id=home_external_team_id,
        away_external_team_id=away_external_team_id,
        home_team_name=home_team_name,
        home_team_abbreviation=home_team_abbreviation,
        away_team_name=away_team_name,
        away_team_abbreviation=away_team_abbreviation,
        scheduled_start_time=scheduled_start_time or datetime.now(timezone.utc),
        status=status,
        season_slug=season_slug,
        season_week=season_week,
        context_label=context_label,
        home_team_record=home_team_record,
        away_team_record=away_team_record,
        home_score=home_score,
        away_score=away_score,
        period=period,
        clock=clock,
        is_final=is_final,
    )


class StaticProvider:
    def __init__(self, games: list[ScoreboardGame] | None = None, *, error: Exception | None = None):
        self.games = games or []
        self.error = error

    def fetch_games(self, competition, requests):
        if self.error is not None:
            raise self.error
        return list(self.games)


class SequenceWorldCupProvider:
    def __init__(
        self,
        snapshots,
        *,
        external_game_id="game-world-cup-live",
        home_external_team_id="660",
        away_external_team_id="203",
    ):
        self._snapshots = list(snapshots)
        self._index = 0
        self._external_game_id = external_game_id
        self._home_external_team_id = home_external_team_id
        self._away_external_team_id = away_external_team_id

    def fetch_games(self, competition, requests):
        snapshot = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return [
            make_game(
                external_game_id=self._external_game_id,
                home_external_team_id=self._home_external_team_id,
                away_external_team_id=self._away_external_team_id,
                status="in_progress",
                home_score=snapshot["home_score"],
                away_score=snapshot["away_score"],
                period=snapshot.get("period", 2),
                clock=snapshot.get("clock", "65'"),
                is_final=False,
            )
        ]


class LongClockProvider:
    def __init__(self, *, home_external_team_id: str, away_external_team_id: str):
        self.home_external_team_id = home_external_team_id
        self.away_external_team_id = away_external_team_id

    def fetch_games(self, competition, requests):
        return [
            make_game(
                external_game_id="game-long-clock",
                home_external_team_id=self.home_external_team_id,
                away_external_team_id=self.away_external_team_id,
                status="in_progress",
                home_score=2,
                away_score=1,
                period=1,
                clock="Rain Delay, Bottom 1st",
                is_final=False,
            )
        ]


class RepeatMatchupProvider:
    def __init__(self, first_start: datetime, second_start: datetime):
        self.first_start = first_start
        self.second_start = second_start

    def fetch_games(self, competition, requests):
        return [
            make_game(
                external_game_id="game-repeat-1",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=self.first_start,
                status="scheduled",
            ),
            make_game(
                external_game_id="game-repeat-2",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=self.second_start,
                status="scheduled",
            ),
        ]


class ContextLabelProvider:
    def __init__(self, context_label: str | None):
        self.context_label = context_label

    def fetch_games(self, competition, requests):
        return [
            make_game(
                external_game_id="game-context",
                home_external_team_id="1",
                away_external_team_id="2",
                status="scheduled",
                context_label=self.context_label,
            )
        ]


class RecordingCatalogProvider:
    def __init__(self, scheduled_start_time: datetime):
        self.scheduled_start_time = scheduled_start_time
        self.requests: list[str] = []

    def fetch_games(self, competition, requests):
        self.requests = list(requests)
        return [
            make_game(
                external_game_id=f"{competition.lower()}-catalog-game",
                home_external_team_id="10" if competition == "MLB" else "660",
                away_external_team_id="2" if competition == "MLB" else "203",
                scheduled_start_time=self.scheduled_start_time,
                status="scheduled",
            )
        ]


def make_success_provider() -> StaticProvider:
    return StaticProvider(
        [
            make_game(
                external_game_id="game-1",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=datetime.now(timezone.utc) + timedelta(hours=1),
                status="scheduled",
            )
        ]
    )


def make_live_close_provider() -> StaticProvider:
    return StaticProvider(
        [
            make_game(
                external_game_id="game-live",
                home_external_team_id="1",
                away_external_team_id="2",
                status="in_progress",
                home_score=100,
                away_score=98,
                period=4,
                clock="01:30",
            )
        ]
    )


def make_final_provider() -> StaticProvider:
    return StaticProvider(
        [
            make_game(
                external_game_id="game-final",
                home_external_team_id="1",
                away_external_team_id="2",
                status="final",
                home_score=110,
                away_score=104,
                period=4,
                clock="00:00",
                is_final=True,
            )
        ]
    )


def make_mlb_inning_provider() -> StaticProvider:
    return StaticProvider(
        [
            make_game(
                external_game_id="game-mlb-live",
                home_external_team_id="2",
                away_external_team_id="10",
                status="in_progress",
                home_score=2,
                away_score=1,
                period=7,
                clock="Top 7th",
            )
        ]
    )
