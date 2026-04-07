from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Game, GameOddsCurrent, IngestRun, SentAlert, Team, User, UserAlertPreference, UserGameFollow, UserTeamFollow
from worker.ingest import run_ingest_cycle
from worker.odds import MoneylineOdds
from worker.providers.base import ProviderGame


class SuccessProvider:
    def __init__(self):
        self.fetch_updates_calls = 0

    def fetch_schedule(self):
        return [
            ProviderGame(
                external_game_id="game-1",
                home_external_team_id="1610612737",
                away_external_team_id="1610612738",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
        ]

    def fetch_game_updates(self, external_game_ids):
        self.fetch_updates_calls += 1
        return []


class FailingProvider:
    def fetch_schedule(self):
        raise RuntimeError("boom")

    def fetch_game_updates(self, external_game_ids):
        return []


class LiveCloseProvider:
    def fetch_schedule(self):
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

    def fetch_game_updates(self, external_game_ids):
        return []


class FinalProvider:
    def fetch_schedule(self):
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

    def fetch_game_updates(self, external_game_ids):
        return []


def test_ingest_run_success(db_session):
    provider = SuccessProvider()
    result = run_ingest_cycle(provider)
    assert result["status"] == "success"
    assert result["games_checked"] == 1
    assert result["games_updated"] == 1
    assert result["next_poll_seconds"] >= 30
    assert provider.fetch_updates_calls == 0

    runs = db_session.scalars(select(IngestRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "success"

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
    user = User(email="alerts@example.com", password_hash="hash")
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
    assert all(row.delivery_status == "sent" for row in sent)


def test_ingest_creates_final_result_alert(db_session):
    user = User(email="final@example.com", password_hash="hash")
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
    assert sent[0].delivery_status == "sent"


def test_ingest_persists_current_odds(db_session, monkeypatch):
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
