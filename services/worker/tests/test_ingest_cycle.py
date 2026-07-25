from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    ApiCallRollupHourly,
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
from app.services.api_usage import record_api_call_event
from app.services.leagues import ensure_league_settings
from worker.ingest import run_catalog_sync, run_live_sync
from worker.odds import OddsOutcome, OddsSnapshot
from worker.planner import build_live_requests
from worker.scoreboard import ScoreboardGame


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


def make_game(
    *,
    external_game_id: str,
    home_external_team_id: str,
    away_external_team_id: str,
    status: str,
    scheduled_start_time: datetime | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    period: int | None = None,
    clock: str | None = None,
    is_final: bool = False,
    context_label: str | None = None,
) -> ScoreboardGame:
    return ScoreboardGame(
        external_game_id=external_game_id,
        home_external_team_id=home_external_team_id,
        away_external_team_id=away_external_team_id,
        scheduled_start_time=scheduled_start_time or datetime.now(timezone.utc),
        status=status,
        context_label=context_label,
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

    def fetch_games(self, league, requests):
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

    def fetch_games(self, league, requests):
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

    def fetch_games(self, league, requests):
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

    def fetch_games(self, league, requests):
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

    def fetch_games(self, league, requests):
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

    def fetch_games(self, league, requests):
        self.requests = list(requests)
        return [
            make_game(
                external_game_id=f"{league.lower()}-catalog-game",
                home_external_team_id="10" if league == "MLB" else "660",
                away_external_team_id="2" if league == "MLB" else "203",
                scheduled_start_time=self.scheduled_start_time,
                status="scheduled",
            )
        ]


class TelemetryRecordingProvider:
    def __init__(self):
        self.contexts: list[bool] = []
        self._db = None

    def set_telemetry_context(self, db, ingest_run_id):
        self._db = db
        self.contexts.append(db is not None)

    def fetch_games(self, league, requests):
        assert self._db is not None
        record_api_call_event(
            self._db,
            service="worker",
            provider="espn",
            endpoint_key="scoreboard",
            attempt_status="success",
        )
        return [
            make_game(
                external_game_id="game-telemetry",
                home_external_team_id="1",
                away_external_team_id="2",
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


def test_ingest_run_success(db_session):
    provider = make_success_provider()
    result = run_catalog_sync(provider)
    assert result["status"] == "success"
    assert result["games_checked"] == 1
    assert result["games_updated"] == 1
    assert result["next_poll_seconds"] >= 30

    games = db_session.scalars(select(Game)).all()
    assert len(games) == 1


def test_ingest_run_failure(db_session):
    result = run_catalog_sync(StaticProvider(error=RuntimeError("boom")))
    assert result["status"] == "failed"
    assert result["next_poll_seconds"] > 0


def test_ingest_attaches_provider_telemetry_context(db_session, monkeypatch):
    provider = TelemetryRecordingProvider()
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)

    result = run_catalog_sync(provider)

    assert result["status"] == "success"
    assert provider.contexts == [True, False]

    rollups = db_session.scalars(select(ApiCallRollupHourly).where(ApiCallRollupHourly.provider == "espn")).all()
    assert len(rollups) == 1
    assert rollups[0].endpoint_key == "scoreboard"
    assert rollups[0].attempt_status == "success"
    assert rollups[0].call_count == 1


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

    first = run_catalog_sync(make_live_close_provider())
    assert first["status"] == "success"
    second = run_catalog_sync(make_live_close_provider())
    assert second["status"] == "success"

    sent = db_session.scalars(select(SentAlert).order_by(SentAlert.alert_type.asc())).all()
    assert len(sent) == 2
    assert sorted([row.alert_type for row in sent]) == ["close_game_late", "game_start"]
    assert all(row.delivery_status == "sent" for row in sent)


def test_nba_overtime_start_alerts_once_per_overtime_period(db_session):
    enabled_user = User(email="overtime@example.com")
    disabled_user = User(email="no-overtime@example.com")
    db_session.add_all([enabled_user, disabled_user])
    db_session.commit()
    db_session.refresh(enabled_user)
    db_session.refresh(disabled_user)

    team = db_session.scalar(select(Team).where(Team.league == "NBA", Team.external_team_id == "1"))
    assert team is not None
    for user, overtime_enabled in ((enabled_user, True), (disabled_user, False)):
        db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
        db_session.add(
            UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=False)
        )
        db_session.add(
            UserAlertDefault(user_id=user.id, league="NBA", alert_type="close_game_late", is_enabled=False)
        )
        db_session.add(
            UserAlertDefault(
                user_id=user.id,
                league="NBA",
                alert_type="overtime_start",
                is_enabled=overtime_enabled,
            )
        )
    db_session.commit()

    def overtime_provider(period: int, *, status: str = "in_progress", is_final: bool = False) -> StaticProvider:
        return StaticProvider(
            [
                make_game(
                    external_game_id="game-overtime",
                    home_external_team_id="1",
                    away_external_team_id="2",
                    status=status,
                    home_score=112 + period,
                    away_score=112 + period,
                    period=period,
                    clock="05:00",
                    is_final=is_final,
                )
            ]
        )

    assert run_catalog_sync(overtime_provider(4))["status"] == "success"
    assert run_catalog_sync(overtime_provider(5))["status"] == "success"
    assert run_catalog_sync(overtime_provider(5))["status"] == "success"
    assert run_catalog_sync(overtime_provider(6))["status"] == "success"
    assert run_catalog_sync(overtime_provider(6))["status"] == "success"
    assert run_catalog_sync(overtime_provider(7, status="final", is_final=True))["status"] == "success"

    alerts = db_session.scalars(
        select(SentAlert)
        .where(SentAlert.user_id == enabled_user.id, SentAlert.alert_type == "overtime_start")
        .order_by(SentAlert.id.asc())
    ).all()
    assert [alert.metadata_json["period"] for alert in alerts] == [5, 6]
    assert [alert.metadata_json["clock"] for alert in alerts] == ["05:00", "05:00"]
    assert [alert.metadata_json["status"] for alert in alerts] == ["in_progress", "in_progress"]
    assert [alert.dedupe_key for alert in alerts] == [
        f"{enabled_user.id}:{alerts[0].game_id}:overtime_start:5",
        f"{enabled_user.id}:{alerts[1].game_id}:overtime_start:6",
    ]

    disabled_alerts = db_session.scalars(
        select(SentAlert).where(
            SentAlert.user_id == disabled_user.id,
            SentAlert.alert_type == "overtime_start",
        )
    ).all()
    assert disabled_alerts == []


def test_ingest_creates_final_result_alert(db_session):
    user = User(email="final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run_catalog_sync(make_final_provider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-final"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="final_result", is_enabled=True))
    db_session.commit()

    result = run_catalog_sync(make_final_provider())
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 1
    assert sent[0].alert_type == "final_result"
    assert sent[0].delivery_status == "sent"


def test_wnba_reuses_deduped_basketball_alerts(db_session):
    user = User(email="wnba-alerts@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WNBA", Team.external_team_id == "9"))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    for alert_type in ("game_start", "close_game_late", "overtime_start", "final_result"):
        db_session.add(
            UserAlertDefault(
                user_id=user.id,
                league="WNBA",
                alert_type=alert_type,
                is_enabled=True,
                close_game_margin_threshold=5 if alert_type == "close_game_late" else None,
                close_game_time_threshold_seconds=120 if alert_type == "close_game_late" else None,
            )
        )
    db_session.commit()

    start = datetime.now(timezone.utc) + timedelta(minutes=1)
    live_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="in_progress",
                home_score=82,
                away_score=79,
                period=4,
                clock="01:12",
            )
        ]
    )
    assert run_catalog_sync(live_provider, league="WNBA")["status"] == "success"
    assert run_catalog_sync(live_provider, league="WNBA")["status"] == "success"

    overtime_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="in_progress",
                home_score=88,
                away_score=88,
                period=5,
                clock="05:00",
            )
        ]
    )
    assert run_catalog_sync(overtime_provider, league="WNBA")["status"] == "success"
    assert run_catalog_sync(overtime_provider, league="WNBA")["status"] == "success"

    final_provider = StaticProvider(
        [
            make_game(
                external_game_id="game-wnba-live",
                home_external_team_id="9",
                away_external_team_id="17",
                scheduled_start_time=start,
                status="final",
                home_score=88,
                away_score=80,
                period=4,
                clock="0:00",
                is_final=True,
            )
        ]
    )
    assert run_catalog_sync(final_provider, league="WNBA")["status"] == "success"
    assert run_catalog_sync(final_provider, league="WNBA")["status"] == "success"

    sent = db_session.scalars(
        select(SentAlert).where(SentAlert.user_id == user.id).order_by(SentAlert.alert_type.asc())
    ).all()
    assert [alert.alert_type for alert in sent] == [
        "close_game_late",
        "final_result",
        "game_start",
        "overtime_start",
    ]


def test_following_live_game_after_start_does_not_send_game_start_alert(db_session):
    user = User(email="late-follow@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-live-late-follow",
                home_external_team_id="1",
                away_external_team_id="2",
                scheduled_start_time=datetime.now(timezone.utc) - timedelta(minutes=10),
                status="in_progress",
                home_score=100,
                away_score=98,
                period=4,
                clock="01:30",
            )
        ]
    )
    assert run_catalog_sync(provider)["status"] == "success"

    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live-late-follow"))
    assert game is not None

    db_session.add(UserGameFollow(user_id=user.id, game_id=game.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.commit()

    result = run_catalog_sync(provider)
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert all(row.alert_type != "game_start" for row in sent)


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

    monkeypatch.setattr("worker.alerts.deliver_alert_now", fake_deliver)

    result = run_catalog_sync(make_live_close_provider())
    assert result["status"] == "success"
    assert result["alerts_created"] == 2

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert len(sent) == 2
    assert all(row.delivery_status == "failed" for row in sent)
    assert all(row.metadata_json["error"] == "synthetic_failure" for row in sent)


def test_live_sync_persists_long_clock_values(db_session):
    teams = db_session.scalars(select(Team).where(Team.league == "NBA").order_by(Team.id.asc())).all()
    result = run_catalog_sync(
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
    assert requests == ["20260610", "20260611"]


def test_ingest_respects_game_override_over_league_default(db_session):
    user = User(email="override@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    teams = db_session.scalars(select(Team).order_by(Team.id.asc())).all()
    db_session.add(UserTeamFollow(user_id=user.id, team_id=teams[0].id))
    db_session.add(UserAlertDefault(user_id=user.id, league="NBA", alert_type="game_start", is_enabled=True))
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
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

    run_catalog_sync(make_live_close_provider())
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

    run_catalog_sync(make_live_close_provider())
    game = db_session.scalar(select(Game).where(Game.external_game_id == "game-live"))
    assert game is not None

    db_session.add(UserGameUnfollow(user_id=user.id, game_id=game.id))
    db_session.commit()

    db_session.query(SentAlert).delete()
    db_session.commit()

    run_catalog_sync(make_live_close_provider())
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

    result = run_catalog_sync(make_mlb_inning_provider(), league="MLB")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert any(row.alert_type == "inning_start" for row in sent)


def test_mlb_extra_innings_alerts_once_per_inning(db_session):
    enabled_user = User(email="extra-innings@example.com")
    disabled_user = User(email="no-extra-innings@example.com")
    db_session.add_all([enabled_user, disabled_user])
    db_session.commit()
    db_session.refresh(enabled_user)
    db_session.refresh(disabled_user)

    team = db_session.scalar(select(Team).where(Team.league == "MLB", Team.external_team_id == "2"))
    assert team is not None
    for user, extra_innings_enabled in ((enabled_user, True), (disabled_user, False)):
        db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
        db_session.add(
            UserAlertDefault(user_id=user.id, league="MLB", alert_type="game_start", is_enabled=False)
        )
        db_session.add(
            UserAlertDefault(user_id=user.id, league="MLB", alert_type="inning_start", is_enabled=False)
        )
        db_session.add(
            UserAlertDefault(
                user_id=user.id,
                league="MLB",
                alert_type="extra_innings_start",
                is_enabled=extra_innings_enabled,
            )
        )
    db_session.commit()

    def extra_innings_provider(
        inning: int,
        *,
        status: str = "in_progress",
        is_final: bool = False,
    ) -> StaticProvider:
        return StaticProvider(
            [
                make_game(
                    external_game_id="game-extra-innings",
                    home_external_team_id="2",
                    away_external_team_id="10",
                    status=status,
                    home_score=3,
                    away_score=3,
                    period=inning,
                    clock=f"Top {inning}th",
                    is_final=is_final,
                )
            ]
        )

    assert run_catalog_sync(extra_innings_provider(9), league="MLB")["status"] == "success"
    assert run_catalog_sync(extra_innings_provider(10), league="MLB")["status"] == "success"
    assert run_catalog_sync(extra_innings_provider(10), league="MLB")["status"] == "success"
    assert run_catalog_sync(extra_innings_provider(11), league="MLB")["status"] == "success"
    assert run_catalog_sync(extra_innings_provider(11), league="MLB")["status"] == "success"
    assert run_catalog_sync(
        extra_innings_provider(12, status="final", is_final=True),
        league="MLB",
    )["status"] == "success"

    alerts = db_session.scalars(
        select(SentAlert)
        .where(SentAlert.user_id == enabled_user.id, SentAlert.alert_type == "extra_innings_start")
        .order_by(SentAlert.id.asc())
    ).all()
    assert [alert.metadata_json["period"] for alert in alerts] == [10, 11]
    assert [alert.metadata_json["clock"] for alert in alerts] == ["Top 10th", "Top 11th"]
    assert [alert.metadata_json["status"] for alert in alerts] == ["in_progress", "in_progress"]
    assert [alert.dedupe_key for alert in alerts] == [
        f"{enabled_user.id}:{alerts[0].game_id}:extra_innings_start:10",
        f"{enabled_user.id}:{alerts[1].game_id}:extra_innings_start:11",
    ]

    disabled_alerts = db_session.scalars(
        select(SentAlert).where(
            SentAlert.user_id == disabled_user.id,
            SentAlert.alert_type == "extra_innings_start",
        )
    ).all()
    assert disabled_alerts == []


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


def test_world_cup_second_half_start_alert_triggers_once_on_resume(db_session):
    user = User(email="world-cup-second-half@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="second_half_start", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "44'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "HT"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "46'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "48'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "second_half_start")).all()
    assert len(sent) == 1
    assert sent[0].metadata_json["period"] == 2
    assert sent[0].metadata_json["clock"] == "46'"


def test_world_cup_second_half_start_does_not_trigger_at_halftime(db_session):
    user = User(email="world-cup-halftime@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="second_half_start", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "44'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "HT"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "second_half_start")).all()
    assert len(sent) == 0


def test_world_cup_extra_time_start_alert_triggers_once_on_period_three_transition(db_session):
    user = User(email="world-cup-extra-time@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="extra_time_start", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "ET"},
            {"home_score": 2, "away_score": 2, "period": 3, "clock": "91'"},
            {"home_score": 2, "away_score": 2, "period": 3, "clock": "94'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "extra_time_start")).all()
    assert len(sent) == 1
    assert sent[0].metadata_json["period"] == 3
    assert sent[0].metadata_json["clock"] == "91'"


def test_world_cup_extra_time_start_does_not_trigger_before_period_three(db_session):
    user = User(email="world-cup-extra-time-blocked@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="extra_time_start", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 2, "clock": "ET"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "extra_time_start")).all()
    assert len(sent) == 0


def test_world_cup_transition_logging_captures_stoppage_and_extra_time_states(db_session, caplog):
    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "ET"},
        ]
    )

    with caplog.at_level("INFO", logger="worker.ingest"):
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    assert "Soccer state transition external_game_id=game-world-cup-live" in caplog.text
    assert "period=2->3" in caplog.text
    assert "90+5'" in caplog.text
    assert "ET" in caplog.text
    assert "extra_time=False->True" in caplog.text
    assert "extra_time_started=True" in caplog.text
    assert "second_half_live=True->False" in caplog.text


def test_world_cup_penalty_kicks_alert_triggers_once_in_late_tied_extra_time(db_session):
    user = User(email="world-cup-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="penalty_kicks", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "117'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "118'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "penalty_kicks")).all()
    assert len(sent) == 1
    assert sent[0].metadata_json["period"] == 3
    assert sent[0].metadata_json["clock"] == "117'"


def test_world_cup_penalty_kicks_alert_does_not_trigger_before_threshold_or_without_tie(db_session):
    user = User(email="world-cup-penalties-blocked@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "WORLD_CUP").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="WORLD_CUP", alert_type="penalty_kicks", is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 2, "away_score": 1, "period": 3, "clock": "117'"},
        ]
    )
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
    result = run_catalog_sync(provider, league="WORLD_CUP")
    assert result["status"] == "success"

    sent = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id, SentAlert.alert_type == "penalty_kicks")).all()
    assert len(sent) == 0


def test_world_cup_transition_logging_marks_penalty_kicks_window(db_session, caplog):
    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "116'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "117'"},
        ]
    )

    with caplog.at_level("INFO", logger="worker.ingest"):
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"
        assert run_catalog_sync(provider, league="WORLD_CUP")["status"] == "success"

    assert "Soccer state transition external_game_id=game-world-cup-live" in caplog.text
    assert "period=3->3" in caplog.text
    assert "penalty_kicks_window=False->True" in caplog.text


def test_mls_direct_shootout_triggers_penalties_without_extra_time_or_score_change(db_session):
    user = User(email="mls-direct-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type="game_start", is_enabled=False))
    for alert_type in ("extra_time_start", "penalty_kicks", "score_changed"):
        db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 2, "away_score": 2, "period": 5, "clock": "93'"},
            {"home_score": 2, "away_score": 2, "period": 5, "clock": "96'"},
        ],
        external_game_id="game-mls-direct-penalties",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(3):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert [alert.alert_type for alert in alerts] == ["penalty_kicks"]
    assert alerts[0].metadata_json["period"] == 5


def test_mls_extra_time_then_shootout_triggers_each_phase_once(db_session):
    user = User(email="mls-extra-time-penalties@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type="game_start", is_enabled=False))
    for alert_type in ("extra_time_start", "penalty_kicks"):
        db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 1, "away_score": 1, "period": 2, "clock": "90+5'"},
            {"home_score": 1, "away_score": 1, "period": 3, "clock": "91'"},
            {"home_score": 1, "away_score": 1, "period": 5, "clock": "Pens"},
            {"home_score": 1, "away_score": 1, "period": 5, "clock": "Pens"},
        ],
        external_game_id="game-mls-extra-time-penalties",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(4):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(
        select(SentAlert).where(SentAlert.user_id == user.id).order_by(SentAlert.id.asc())
    ).all()
    assert [alert.alert_type for alert in alerts] == ["extra_time_start", "penalty_kicks"]


def test_mls_second_half_and_goal_use_shared_soccer_events(db_session):
    user = User(email="mls-shared-soccer-events@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type="game_start", is_enabled=False))
    for alert_type in ("second_half_start", "score_changed"):
        db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type=alert_type, is_enabled=True))
    db_session.commit()

    provider = SequenceWorldCupProvider(
        [
            {"home_score": 0, "away_score": 0, "period": 1, "clock": "45+2'"},
            {"home_score": 0, "away_score": 0, "period": 2, "clock": "46'"},
            {"home_score": 1, "away_score": 0, "period": 2, "clock": "52'"},
        ],
        external_game_id="game-mls-shared-soccer-events",
        home_external_team_id="187",
        away_external_team_id="18966",
    )
    for _ in range(3):
        assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(
        select(SentAlert).where(SentAlert.user_id == user.id).order_by(SentAlert.id.asc())
    ).all()
    assert [alert.alert_type for alert in alerts] == ["second_half_start", "score_changed"]
    assert alerts[1].metadata_json["scoring_side"] == "home"


def test_mls_final_result_uses_shared_soccer_alert_set(db_session):
    user = User(email="mls-final@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    team = db_session.scalar(select(Team).where(Team.league == "MLS").order_by(Team.id.asc()))
    assert team is not None
    db_session.add(UserTeamFollow(user_id=user.id, team_id=team.id))
    db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type="game_start", is_enabled=False))
    db_session.add(UserAlertDefault(user_id=user.id, league="MLS", alert_type="final_result", is_enabled=True))
    db_session.commit()

    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-mls-final",
                home_external_team_id="187",
                away_external_team_id="18966",
                status="final",
                home_score=2,
                away_score=1,
                period=2,
                clock="FT",
                is_final=True,
            )
        ]
    )
    assert run_catalog_sync(provider, league="MLS")["status"] == "success"

    alerts = db_session.scalars(select(SentAlert).where(SentAlert.user_id == user.id)).all()
    assert [alert.alert_type for alert in alerts] == ["final_result"]


def test_ingest_persists_current_odds(db_session, monkeypatch):
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
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

    result = run_catalog_sync(make_success_provider())
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
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=120, home_label="Boston Celtics", home_price=-140, bookmaker="FanDuel", last_update=now, commence_time=first_start),
                make_snapshot(away_label="Atlanta Hawks", away_price=175, home_label="Boston Celtics", home_price=-210, bookmaker="FanDuel", last_update=now, commence_time=second_start),
            ]
        },
    )

    result = run_catalog_sync(provider)
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
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=122, home_label="Boston Celtics", home_price=-145, bookmaker="FanDuel", last_update=now, commence_time=first_start)
            ]
        },
    )

    result = run_catalog_sync(provider)
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
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", True)
    monkeypatch.setattr("worker.ingest.fetch_odds_index", lambda league: {})

    result = run_catalog_sync(make_success_provider())
    assert result["status"] == "success"

    assert result["next_poll_seconds"] > 0


def test_catalog_sync_creates_single_pregame_odds_snapshot(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-catalog", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    odds_fetch_count = {"count": 0}

    def _fake_odds_index(league):
        odds_fetch_count["count"] += 1
        return {
            ("atlanta hawks", "boston celtics"): [
                make_snapshot(away_label="Atlanta Hawks", away_price=110, home_label="Boston Celtics", home_price=-130, last_update=now, commence_time=now + timedelta(hours=4))
            ]
        }

    monkeypatch.setattr("worker.ingest.fetch_odds_index", _fake_odds_index)

    first = run_catalog_sync(provider)
    second = run_catalog_sync(provider)

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
    assert provider.requests == [
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

    provider = StaticProvider(
        [
            make_game(
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
    )

    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched in live sync")),
    )

    result = run_live_sync(provider)
    assert result["status"] == "success"
    assert result["games_updated"] >= 1


def test_catalog_sync_skips_odds_when_disabled(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [make_game(external_game_id="game-no-odds", home_external_team_id="1", away_external_team_id="2", scheduled_start_time=now + timedelta(hours=4), status="scheduled")]
    )

    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)
    monkeypatch.setattr(
        "worker.ingest.fetch_odds_index",
        lambda league: (_ for _ in ()).throw(AssertionError("odds should not be fetched when disabled")),
    )

    result = run_catalog_sync(provider)
    assert result["status"] == "success"
    assert result["odds_candidates"] == 0
    assert result["odds_snapshots_created"] == 0


def test_world_cup_catalog_sync_persists_three_way_odds(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="game-world-cup-scheduled",
                home_external_team_id="660",
                away_external_team_id="203",
                scheduled_start_time=now + timedelta(hours=3),
                status="scheduled",
                is_final=False,
            )
        ]
    )

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

    result = run_catalog_sync(provider, league="WORLD_CUP")
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

    result = run_live_sync(StaticProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_live_sync_returns_no_upcoming_when_schedule_empty(db_session):
    result = run_live_sync(StaticProvider(), league="MLB")
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

    result = run_live_sync(StaticProvider(), league="MLB")
    assert result["status"] == "success"
    assert result["has_live_games"] == "false"
    assert result["mode"] == "waiting_for_start"
    assert result["next_scheduled_start_at"] is not None


def test_catalog_sync_fails_for_disabled_league(db_session):
    ensure_league_settings(db_session)
    row = db_session.get(LeagueSetting, "MLB")
    assert row is not None
    row.is_enabled = False
    db_session.commit()

    result = run_catalog_sync(StaticProvider(), league="MLB")
    assert result["status"] == "failed"


def test_catalog_sync_fails_when_no_provider_games_map_to_teams(db_session):
    provider = StaticProvider(
        [
            make_game(
                external_game_id="mls-unmapped",
                home_external_team_id="unknown-home",
                away_external_team_id="unknown-away",
                status="scheduled",
            )
        ]
    )

    result = run_catalog_sync(provider, league="MLS")

    assert result["status"] == "failed"
    assert result["error"] == "No MLS games could be mapped to catalog teams"
    assert db_session.scalar(select(Game).where(Game.league == "MLS")) is None


def test_catalog_sync_allows_partial_team_mapping(db_session, monkeypatch):
    monkeypatch.setattr("worker.ingest.settings.odds_enabled", False)
    provider = StaticProvider(
        [
            make_game(
                external_game_id="mls-mapped",
                home_external_team_id="187",
                away_external_team_id="18966",
                status="scheduled",
            ),
            make_game(
                external_game_id="mls-all-star",
                home_external_team_id="unknown-home",
                away_external_team_id="unknown-away",
                status="scheduled",
            ),
        ]
    )

    result = run_catalog_sync(provider, league="MLS")

    assert result["status"] == "success"
    assert result["games_checked"] == 2
    assert result["games_updated"] == 1
    games = db_session.scalars(select(Game).where(Game.league == "MLS")).all()
    assert [game.external_game_id for game in games] == ["mls-mapped"]


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

    provider = StaticProvider(
        [
            make_game(
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
    )

    result = run_live_sync(provider, league="MLB")
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
