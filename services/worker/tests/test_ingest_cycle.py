from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    Game,
    GameOddsCurrent,
    GameOddsOutcomeCurrent,
    LeagueSetting,
    SentAlert,
    Team,
    User,
    UserAlertDefault,
    UserGameAlertOverride,
    UserGameFollow,
    UserGameUnfollow,
    UserTeamFollow,
)
from app.services.leagues import ensure_league_settings
from worker.ingest import run_catalog_sync, run_ingest_cycle, run_live_sync
from worker.odds import OddsOutcome, OddsSnapshot
from worker.planner import FetchPlan, build_live_requests
from worker.providers.base import ProviderGame, ScoreboardRequest


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
        market="h2h",
        outcomes=tuple(outcomes),
        bookmaker=bookmaker,
        last_update=last_update,
        commence_time=commence_time,
    )


class SuccessProvider:
    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-1",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class FailingProvider:
    def fetch_games(self, league, requests):
        raise RuntimeError("boom")

    def expected_call_count(self, requests):
        return len(requests)


class LiveCloseProvider:
    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-live",
                home_external_team_id="1",
                away_external_team_id="2",
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
    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-final",
                home_external_team_id="1",
                away_external_team_id="2",
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


class MlbInningProvider:
    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-mlb-live",
                home_external_team_id="2",
                away_external_team_id="10",
                scheduled_start_time=datetime.now(timezone.utc),
                status="in_progress",
                home_score=2,
                away_score=1,
                period=7,
                clock="Top 7th",
                is_final=False,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class WorldCupProvider:
    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-world-cup-live",
                home_external_team_id="660",
                away_external_team_id="203",
                scheduled_start_time=datetime.now(timezone.utc),
                status="in_progress",
                home_score=1,
                away_score=0,
                period=2,
                clock="65'",
                is_final=False,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class SequenceWorldCupProvider:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)
        self._index = 0

    def fetch_games(self, league, requests):
        snapshot = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return [
            ProviderGame(
                external_game_id="game-world-cup-live",
                home_external_team_id="660",
                away_external_team_id="203",
                scheduled_start_time=datetime.now(timezone.utc),
                status="in_progress",
                home_score=snapshot["home_score"],
                away_score=snapshot["away_score"],
                period=snapshot.get("period", 2),
                clock=snapshot.get("clock", "65'"),
                is_final=False,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class LongClockProvider:
    def __init__(self, *, home_external_team_id: str, away_external_team_id: str):
        self.home_external_team_id = home_external_team_id
        self.away_external_team_id = away_external_team_id

    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-long-clock",
                home_external_team_id=self.home_external_team_id,
                away_external_team_id=self.away_external_team_id,
                scheduled_start_time=datetime.now(timezone.utc),
                status="in_progress",
                home_score=2,
                away_score=1,
                period=1,
                clock="Rain Delay, Bottom 1st",
                is_final=False,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class RepeatMatchupProvider:
    def __init__(self, first_start: datetime, second_start: datetime):
        self.first_start = first_start
        self.second_start = second_start

    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-repeat-1",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=self.first_start,
                status="scheduled",
            ),
            ProviderGame(
                external_game_id="game-repeat-2",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=self.second_start,
                status="scheduled",
            ),
        ]

    def expected_call_count(self, requests):
        return len(requests)


class ContextLabelProvider:
    def __init__(self, context_label: str | None):
        self.context_label = context_label

    def fetch_games(self, league, requests):
        return [
            ProviderGame(
                external_game_id="game-context",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=datetime.now(timezone.utc),
                status="scheduled",
                context_label=self.context_label,
            )
        ]

    def expected_call_count(self, requests):
        return len(requests)


class RecordingCatalogProvider:
    def __init__(self, scheduled_start_time: datetime):
        self.scheduled_start_time = scheduled_start_time
        self.requests: list[ScoreboardRequest] = []

    def fetch_games(self, league, requests):
        self.requests = list(requests)
        return [
            ProviderGame(
                external_game_id=f"{league.lower()}-catalog-game",
                home_external_team_id="10" if league == "MLB" else "660",
                away_external_team_id="4" if league == "MLB" else "203",
                scheduled_start_time=self.scheduled_start_time,
                status="scheduled",
            )
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

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    result = run_ingest_cycle(FailingProvider())
    assert result["status"] == "failed"
    assert result["next_poll_seconds"] > 0


def test_ingest_creates_deduped_live_alerts(db_session):
    user = User(email="alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.add(
        UserAlertDefault(
            user_id=user.id,
            league="NBA",
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
    user = User(email="final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run_ingest_cycle(FinalProvider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-final"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="final_result", is_enabled=True))
    db_session.commit()

    result = run_ingest_cycle(FinalProvider())
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 1
    assert sent[0].alert_type == "final_result"
    assert sent[0].delivery_status == "sent"


def test_ingest_continues_when_inline_delivery_fails(db_session, monkeypatch):
    user = User(email="inline-fail@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.commit()

    def fake_deliver(db, *, alert, user, game, home, away, service, ingest_run_id=None):
        alert.delivery_status = "failed"
        alert.metadata_json = {**(alert.metadata_json or {}), "error": "synthetic_failure"}
        return "failed"

    monkeypatch.setattr("worker.ingest.deliver_alert_now", fake_deliver)

    result = run_ingest_cycle(LiveCloseProvider())
    assert result["status"] == "success"
    assert result["alerts_created"] == 2

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 2
    assert all(row.delivery_status == "failed" for row in sent)
    assert all(row.metadata_json["error"] == "synthetic_failure" for row in sent)


def test_live_sync_persists_long_clock_values(db_session):
    teams = db_session.scalars(select(Team).where(Team.league == "NBA").order_by(Team.id.asc())).all()
    result = run_ingest_cycle(
        LongClockProvider(
            home_external_team_id=teams[0].external_team_id,
            away_external_team_id=teams[1].external_team_id,
        )
    )
    assert result["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-long-clock"))
    assert game is not None
    assert game.clock == "Rain Delay, Bottom 1st"


def test_build_live_requests_includes_previous_scoreboard_date_for_midnight_utc_games(db_session):
    teams = db_session.scalars(select(Team).where(Team.league == "NBA").order_by(Team.id.asc())).all()
    now = datetime(2026, 6, 11, 1, 0, tzinfo=timezone.utc)
    db_session.add(
        Game(
            external_game_id="nba-midnight-utc",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=datetime(2026, 6, 11, 0, 30, tzinfo=timezone.utc),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    requests = build_live_requests(db_session, "NBA", now=now)
    assert [request.date for request in requests] == ["20260610", "20260611"]


def test_ingest_respects_game_override_over_league_default(db_session):
    user = User(email="override@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.commit()

    run_ingest_cycle(LiveCloseProvider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live"))
    assert game is not None

    db_session.add(
        UserGameAlertOverride(
            user_id=user.id,
            game_id=game.id,
            alert_type="game_start",
            is_enabled_override=False,
        )
    )
    db_session.commit()

    db_session.query(SentAlert).delete()
    db_session.commit()

    run_ingest_cycle(LiveCloseProvider())
    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert all(row.alert_type != "game_start" for row in sent)


def test_ingest_excludes_user_game_unfollows_for_team_follows(db_session):
    user = User(email="unfollow-override@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.commit()

    run_ingest_cycle(LiveCloseProvider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live"))
    assert game is not None

    db_session.add(UserGameUnfollow(user_id=user.id, game_id=game.id))
    db_session.commit()

    db_session.query(SentAlert).delete()
    db_session.commit()

    run_ingest_cycle(LiveCloseProvider())
    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 0


def test_ingest_creates_mlb_inning_start_alert(db_session):
    user = User(email="mlb-inning@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    mlb_team = db_session.scalar(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()))
    assert mlb_team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=mlb_team.id))
    db_session.add(
        UserAlertDefault(
            user_id=user.id,
            league="MLB",
            alert_type="inning_start",
            is_enabled=True,
            inning_start_threshold=7,
        )
    )
    db_session.commit()

    result = run_catalog_sync(MlbInningProvider(), league="MLB")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert any(row.alert_type == "inning_start" for row in sent)


def test_world_cup_score_changed_creates_inferred_goal_alert(db_session):
    user = User(email="world-cup-score@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "10'"},
            {"home_score": 0, "away_score": 1, "period": 1, "clock": "18'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "score_changed")).all()
    assert len(sent) == 1
    assert sent[0].metadata_json["is_inferred_goal"] is True
    assert sent[0].metadata_json["scoring_side"] == "away"
    assert sent[0].metadata_json["new_away_score"] == 1
    assert sent[0].metadata_json["new_home_score"] == 0


def test_world_cup_score_changed_creates_generic_alert_for_ambiguous_jump(db_session):
    user = User(email="world-cup-score-ambiguous@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "60'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "68'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "score_changed")).all()
    assert len(sent) == 1
    assert sent[0].metadata_json["is_inferred_goal"] is False
    assert sent[0].metadata_json["scoring_side"] is None


def test_world_cup_score_changed_ignores_score_decreases(db_session):
    user = User(email="world-cup-score-decrease@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="score_changed", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "60'"},
            {"home_score": 1, "away_score": 0, "period": 2, "clock": "61'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "score_changed")).all()
    assert len(sent) == 0


def test_ingest_persists_current_odds(db_session, monkeypatch):
    monkeypatch.setattr(
        "worker.ingest.build_fetch_plan",
        lambda db: FetchPlan(
            mode="active",
            next_ingest_seconds=300,
            espn_requests=[ScoreboardRequest(date="20260416")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=1,
            expected_odds_calls=1,
        ),
    )
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): make_snapshot(
                away_label="Atlanta Hawks",
                away_price=110,
                home_label="Boston Celtics",
                home_price=-130,
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
    assert [(item.team_side, item.price_american) for item in odds.outcomes] == [("away", 110), ("home", -130)]


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
            espn_requests=[ScoreboardRequest(date="20260416"), ScoreboardRequest(date="20260417")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=2,
            expected_odds_calls=1,
        ),
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=120, home_label="Boston Celtics", home_price=-140, bookmaker="FanDuel", last_update=now, commence_time=first_start),
                make_snapshot(away_label="Atlanta Hawks", away_price=175, home_label="Boston Celtics", home_price=-210, bookmaker="FanDuel", last_update=now, commence_time=second_start),
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
    assert [(item.team_side, item.price_american) for item in first_odds.outcomes] == [("away", 120), ("home", -140)]


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
            espn_requests=[ScoreboardRequest(date="20260416"), ScoreboardRequest(date="20260417")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=2,
            expected_odds_calls=1,
        ),
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=122, home_label="Boston Celtics", home_price=-145, bookmaker="FanDuel", last_update=now, commence_time=first_start)
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
            espn_requests=[ScoreboardRequest(date="20260416")],
            odds_refresh=True,
            odds_refresh_reason="forced_for_test",
            expected_espn_calls=1,
            expected_odds_calls=1,
        ),
    )
    monkeypatch.setattr("worker.ingest.fetch_odds_index", lambda league: {})

    result = run_ingest_cycle(SuccessProvider())
    assert result["status"] == "success"

    assert result["next_poll_seconds"] > 0


def test_catalog_sync_creates_single_pregame_odds_snapshot(db_session, monkeypatch):
    now = datetime.now(timezone.utc)

    class CatalogProvider:
        def fetch_games(self, league, requests):
            return [
                ProviderGame(
                    external_game_id="game-catalog",
                    home_external_team_id="1",
                    away_external_team_id="2",
                    scheduled_start_time=now + timedelta(hours=4),
                    status="scheduled",
                )
            ]

        def expected_call_count(self, requests):
            return len(requests)

    odds_fetch_count = {"count": 0}

    def _fake_odds_index(league):
        odds_fetch_count["count"] += 1
        return {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=110, home_label="Boston Celtics", home_price=-130, last_update=now, commence_time=now + timedelta(hours=4))
            ]
        }

    monkeypatch.setattr("worker.ingest.fetch_odds_index", _fake_odds_index)

    first = run_catalog_sync(CatalogProvider())
    second = run_catalog_sync(CatalogProvider())

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert first["odds_snapshots_created"] == 1
    assert second["odds_snapshots_created"] == 0


def test_catalog_sync_uses_fixed_horizon_even_with_existing_games(db_session, monkeypatch):
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    mlb_teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id="mlb-existing",
            league="MLB",
            home_team_id=mlb_teams[0].id,
            away_team_id=mlb_teams[1].id,
            scheduled_start_time=now + timedelta(days=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    provider = RecordingCatalogProvider(now + timedelta(days=3))
    monkeypatch.setattr("worker.ingest.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda tz=None: now)}))
    monkeypatch.setattr("worker.planner.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda tz=None: now)}))

    result = run_catalog_sync(provider, league="MLB")

    assert result["status"] == "success"
    assert [request.date for request in provider.requests] == [
        "20260617",
        "20260618",
        "20260619",
        "20260620",
        "20260621",
        "20260622",
        "20260623",
        "20260624",
        "20260625",
    ]


def test_live_sync_does_not_fetch_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(
        Game(
            external_game_id="game-live-only",
            league="NBA",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now,
            status="live",
            is_final=False,
        )
    )
    db_session.commit()

    class LiveProvider:
        def fetch_games(self, league, requests):
            return [
                ProviderGame(
                    external_game_id="game-live-only",
                    home_external_team_id="1",
                    away_external_team_id="2",
                    scheduled_start_time=now,
                    status="in_progress",
                    home_score=101,
                    away_score=99,
                    period=4,
                    clock="01:15",
                )
            ]

        def expected_call_count(self, requests):
            return len(requests)

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched in live sync")),
    )

    result = run_live_sync(LiveProvider())
    assert result["status"] == "success"
    assert result["games_updated"] >= 1


def test_catalog_sync_skips_odds_when_disabled(db_session, monkeypatch):
    now = datetime.now(timezone.utc)

    class CatalogProvider:
        def fetch_games(self, league, requests):
            return [
                ProviderGame(
                    external_game_id="game-no-odds",
                    home_external_team_id="1",
                    away_external_team_id="2",
                    scheduled_start_time=now + timedelta(hours=4),
                    status="scheduled",
                )
            ]

        def expected_call_count(self, requests):
            return len(requests)

    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched when disabled")),
    )

    result = run_catalog_sync(CatalogProvider())
    assert result["status"] == "success"
    assert result["odds_candidates"] == 0
    assert result["odds_snapshots_created"] == 0


def test_world_cup_catalog_sync_persists_three_way_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)

    class ScheduledWorldCupProvider:
        def fetch_games(self, league, requests):
            return [
                ProviderGame(
                    external_game_id="game-world-cup-scheduled",
                    home_external_team_id="660",
                    away_external_team_id="203",
                    scheduled_start_time=now + timedelta(hours=3),
                    status="scheduled",
                    is_final=False,
                )
            ]

        def expected_call_count(self, requests):
            return len(requests)

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("united states", "mexico"): [
                make_snapshot(
                    away_label="Mexico",
                    away_price=180,
                    home_label="United States",
                    home_price=160,
                    draw_price=210,
                    last_update=now,
                    commence_time=now + timedelta(hours=3),
                )
            ]
        },
    )

    result = run_catalog_sync(ScheduledWorldCupProvider(), league="WORLD_CUP")
    assert result["status"] == "success"
    assert result["odds_snapshots_created"] == 1

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-world-cup-scheduled"))
    assert game is not None
    odds = db_session.scalar(select(GameOddsCurrent).where(GameOddsCurrent.game_id == game.id))
    assert odds is not None
    assert [(item.outcome_key, item.price_american) for item in odds.outcomes] == [
        ("mexico", 180),
        ("draw", 210),
        ("united_states", 160),
    ]


def test_live_sync_returns_next_scheduled_start_when_no_live_games(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-upcoming-1",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now + timedelta(hours=2),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    class EmptyProvider:
        def fetch_games(self, league, requests):
            return []

        def expected_call_count(self, requests):
            return len(requests)

    result = run_live_sync(EmptyProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_live_sync_returns_no_upcoming_when_schedule_empty(db_session):
    class EmptyProvider:
        def fetch_games(self, league, requests):
            return []

        def expected_call_count(self, requests):
            return len(requests)

    result = run_live_sync(EmptyProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "no_upcoming"
    assert result["next_scheduled_start_at"] is None


def test_live_sync_keeps_recently_overdue_scheduled_games_hot(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-overdue-1",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(minutes=20),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    class EmptyProvider:
        def fetch_games(self, league, requests):
            return []

        def expected_call_count(self, requests):
            return len(requests)

    result = run_live_sync(EmptyProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_catalog_sync_fails_for_disabled_league(db_session):
    class DisabledProvider:
        def fetch_games(self, league, requests):
            return []

        def expected_call_count(self, requests):
            return len(requests)

    ensure_league_settings(db_session)
    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    result = run_catalog_sync(DisabledProvider(), league="MLB")
    assert result["status"] == "failed"


def test_live_sync_promotes_scheduled_game_to_live(db_session):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    teams = db_session.scalars(select(Team).where(Team.league == "MLB").order_by(Team.id.asc()).limit(2)).all()
    db_session.add(
        Game(
            external_game_id="mlb-angels-like",
            league="MLB",
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            scheduled_start_time=now - timedelta(minutes=15),
            status="scheduled",
            is_final=False,
        )
    )
    db_session.commit()

    class PromoteProvider:
        def fetch_games(self, league, requests):
            return [
                ProviderGame(
                    external_game_id="mlb-angels-like",
                    home_external_team_id=teams[0].external_team_id,
                    away_external_team_id=teams[1].external_team_id,
                    scheduled_start_time=now - timedelta(minutes=15),
                    status="in_progress",
                    home_score=1,
                    away_score=0,
                    period=2,
                    clock="Top 2nd",
                    is_final=False,
                )
            ]

        def expected_call_count(self, requests):
            return len(requests)

    result = run_live_sync(PromoteProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "true"
    assert result["mode"] == "live"
    assert result["games_updated"] >= 1

    db_session.expire_all()
    game = db_session.scalar(select(Game).where(Game.external_game_id == "mlb-angels-like", Game.league == "MLB"))
    assert game is not None
    assert game.status == "in_progress"


def test_ingest_persists_and_refreshes_context_label(db_session):
    first = run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · NY leads series 3-1"), league="NBA")
    assert first["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-context"))
    assert game is not None
    assert game.context_label == "NBA Finals - Game 5 · NY leads series 3-1"

    second = run_catalog_sync(ContextLabelProvider("NBA Finals - Game 5 · Series tied 3-3"), league="NBA")
    assert second["status"] == "success"

    db_session.refresh(game)
    assert game.context_label == "NBA Finals - Game 5 · Series tied 3-3"
