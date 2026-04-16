from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, IngestRun, SentAlert, Team, User, UserAlertPreference, UserGameFollow, UserTeamFollow
from worker.ingest import run_ingest_cycle
from worker.odds import MoneylineOdds
from worker.planner import FetchPlan
from worker.providers.base import EspnRequest, ProviderGame


class SuccessProvider:
    def fetch_games(self, requests):
        return [
            ProviderGame(
                external_game_id="game-1",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class FailingProvider:
    def fetch_games(self, requests):
        raise RuntimeError("boom")

    def expected_call_count(self, requests):
        return len(requests)


class LiveCloseProvider:
    def fetch_games(self, requests):
        return [
            ProviderGame(
                external_game_id="game-live",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="in_progress",
                home_score=100,
                away_score=98,
                period=4,
                clock="01:30",
                is_final=False,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class FinalProvider:
    def fetch_games(self, requests):
        return [
            ProviderGame(
                external_game_id="game-final",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="final",
                home_score=110,
                away_score=104,
                period=4,
                clock="00:00",
                is_final=True,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class RepeatMatchupProvider:
    def __init__(self, first_start: datetime, second_start: datetime):
        self.first_start = first_start
        self.second_start = second_start

    def fetch_games(self, requests):
        return [
            ProviderGame(
                external_game_id="game-repeat-1",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=self.first_start,
                status="scheduled",
            ),
            ProviderGame(
                external_game_id="game-repeat-2",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=self.second_start,
                status="scheduled",
            ),
        ]

    def expected_call_count(self, requests):
        return len(requests)


def test_ingest_run_success(db_session):
    provider = SuccessProvider()
    result = run_ingest_cycle(provider)
    assert result["status"] == "success"
    assert result["games_checked"] == 1
    assert result["games_updated"] == 1
    assert result["next_poll_seconds"] >= 30

    runs = db_session.scalars(select(IngestRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].expected_espn_calls == 1
    assert runs[0].expected_odds_calls in {0, 1}
    assert runs[0].actual_espn_calls == 0
    assert runs[0].poll_mode in {"live", "active", "idle"}

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    result = run_ingest_cycle(FailingProvider())
    assert result["status"] == "failed"
    assert result["next_poll_seconds"] > 0

    runs = db_session.scalars(select(IngestRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "failed"


def test_ingest_creates_deduped_live_alerts(db_session):
    user = User(email="alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertPreference(user_id=user.id, alert_type="game_start", is_enabled=True))
    db_session.add(
        UserAlertPreference(
            user_id=user.id,
            alert_type="close_game_late",
            is_enabled=True,
            close_game_margin_threshold=5,
            close_game_time_threshold_seconds=120,
        )
    )
    db_session.commit()

    first = run_ingest_cycle(LiveCloseProvider())
    assert first["status"] == "success"
    second = run_ingest_cycle(LiveCloseProvider())
    assert second["status"] == "success"

    sent = db_session.scalars(select(SentAlert).order_by(SentAlert.alert_type.asc())).all()
    assert len(sent) == 2
    assert sorted([row.alert_type for row in sent]) == ["close_game_late", "game_start"]
    assert all(row.delivery_status == "pending" for row in sent)


def test_ingest_creates_final_result_alert(db_session):
    user = User(email="final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run_ingest_cycle(FinalProvider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-final"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertPreference(user_id=user.id, alert_type="final_result", is_enabled=True))
    db_session.commit()

    result = run_ingest_cycle(FinalProvider())
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 1
    assert sent[0].alert_type == "final_result"
    assert sent[0].delivery_status == "pending"


def test_ingest_persists_current_odds(db_session, monkeypatch):
    monkeypatch.setattr(
        "worker.ingest.build_fetch_plan",
        lambda db: FetchPlan(
            mode="active",
            next_ingest_seconds=300,
            espn_requests=[EspnRequest(date="20260416")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=1,
            expected_odds_calls=1,
        ),
    )
    monkeypatch.setattr(
        "worker.ingest.fetch_nba_odds_index",
        lambda: {
            ("atlanta hawks", "boston celtics"): MoneylineOdds(
                home_moneyline=-130,
                away_moneyline=110,
                bookmaker="DraftKings",
                last_update=datetime.now(timezone.utc),
            )
        },
    )

    result = run_ingest_cycle(SuccessProvider())
    assert result["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-1"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert odds.home_moneyline == -130
    assert odds.away_moneyline == 110


def test_ingest_matches_repeat_matchup_odds_by_commence_time(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_start = now + timedelta(hours=2)
    second_start = now + timedelta(days=2, hours=2)
    provider = RepeatMatchupProvider(first_start=first_start, second_start=second_start)
    monkeypatch.setattr(
        "worker.ingest.build_fetch_plan",
        lambda db: FetchPlan(
            mode="active",
            next_ingest_seconds=300,
            espn_requests=[EspnRequest(date="20260416"), EspnRequest(date="20260417")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=2,
            expected_odds_calls=1,
        ),
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_nba_odds_index",
        lambda: {
            ("atlanta hawks", "boston celtics"): [
                MoneylineOdds(
                    home_moneyline=-140,
                    away_moneyline=120,
                    bookmaker="FanDuel",
                    last_update=now,
                    commence_time=first_start,
                ),
                MoneylineOdds(
                    home_moneyline=-210,
                    away_moneyline=175,
                    bookmaker="FanDuel",
                    last_update=now,
                    commence_time=second_start,
                ),
            ]
        },
    )

    result = run_ingest_cycle(provider)
    assert result["status"] == "success"

    first_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-1"))
    second_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-2"))
    assert first_game is not None
    assert second_game is not None

    first_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first_game.id))
    second_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second_game.id))
    assert first_odds is not None
    assert second_odds is not None
    assert first_odds.home_moneyline == -140
    assert first_odds.away_moneyline == 120
    assert second_odds.home_moneyline == -210
    assert second_odds.away_moneyline == 175


def test_ingest_does_not_apply_far_away_matchup_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_start = now + timedelta(hours=2)
    second_start = now + timedelta(days=2, hours=2)
    provider = RepeatMatchupProvider(first_start=first_start, second_start=second_start)
    monkeypatch.setattr(
        "worker.ingest.build_fetch_plan",
        lambda db: FetchPlan(
            mode="active",
            next_ingest_seconds=300,
            espn_requests=[EspnRequest(date="20260416"), EspnRequest(date="20260417")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=2,
            expected_odds_calls=1,
        ),
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_nba_odds_index",
        lambda: {
            ("atlanta hawks", "boston celtics"): [
                MoneylineOdds(
                    home_moneyline=-145,
                    away_moneyline=122,
                    bookmaker="FanDuel",
                    last_update=now,
                    commence_time=first_start,
                )
            ]
        },
    )

    result = run_ingest_cycle(provider)
    assert result["status"] == "success"

    first_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-1"))
    second_game = db_session.scalar(select(Game).where(Game.external_game_id == "game-repeat-2"))
    assert first_game is not None
    assert second_game is not None

    first_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == first_game.id))
    second_odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == second_game.id))
    assert first_odds is not None
    assert second_odds is None


def test_ingest_expected_odds_calls_tracks_refresh_decision(db_session, monkeypatch):
    monkeypatch.setattr(
        "worker.ingest.build_fetch_plan",
        lambda db: FetchPlan(
            mode="active",
            next_ingest_seconds=300,
            espn_requests=[EspnRequest(date="20260416")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=1,
            expected_odds_calls=1,
        ),
    )
    monkeypatch.setattr("worker.ingest.fetch_nba_odds_index", lambda: {})

    result = run_ingest_cycle(SuccessProvider())
    assert result["status"] == "success"

    run = db_session.scalar(select(IngestRun).order_by(IngestRun.id.desc()))
    assert run is not None
    assert run.expected_odds_calls == 1
