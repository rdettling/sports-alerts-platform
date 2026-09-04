import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.db import usage
from app.db.session import SessionLocal


@pytest.fixture
def counters(monkeypatch):
    monkeypatch.setattr(usage, "_enabled", True)
    usage._counts.clear()
    usage._minutes.clear()
    yield
    usage._counts.clear()
    usage._minutes.clear()


def summaries(caplog):
    return [
        json.loads(record.message.split("Database usage ", 1)[1])
        for record in caplog.records
        if "Database usage {" in record.message
    ]


def test_route_attribution_cache_hits_and_health_do_not_add_database_work(
    client, counters, caplog
):
    with caplog.at_level("INFO", logger=usage.__name__):
        client.get("/games?include_finals=true&limit=500")
        client.get("/games?include_finals=true&limit=500")
        client.get("/healthz")
        usage.flush_usage()
    sources = summaries(caplog)[0]["sources"]
    games = sources["api:GET /games"]
    assert games["connections"] == 1
    assert games["statements"] >= 1
    assert games["game_cache_hits"] == 1
    assert games["game_cache_fills"] == 1
    assert games["db_minutes"]
    assert "api:GET /healthz" not in sources
    assert "include_finals" not in caplog.text


def test_source_isolation_templates_errors_and_no_sql_logging(counters, caplog):
    async def endpoint(scope, receive, send):
        scope["route"] = SimpleNamespace(path=scope["template"])
        await asyncio.sleep(0)
        with SessionLocal() as db:
            db.execute(text("SELECT 'private-value'"))

    middleware = usage.DatabaseUsageMiddleware(endpoint)

    async def scenario():
        await asyncio.gather(
            *[
                middleware(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": f"/games/{i}",
                        "template": template,
                    },
                    None,
                    None,
                )
                for i, template in enumerate(["/games/{game_id}", "/teams/{team_id}"])
            ]
        )

    with caplog.at_level("INFO", logger=usage.__name__):
        asyncio.run(scenario())
        with usage.database_source("worker:live_sync:NBA"):
            with SessionLocal() as db:
                with pytest.raises(Exception):
                    db.execute(text("SELECT * FROM missing_table"))
        usage.flush_usage()
    sources = summaries(caplog)[0]["sources"]
    assert sources["api:GET /games/{game_id}"]["statements"] == 1
    assert sources["api:GET /teams/{team_id}"]["statements"] == 1
    assert sources["worker:live_sync:NBA"]["errors"] == 1
    assert "private-value" not in caplog.text
    assert "missing_table" not in caplog.text
    assert usage._source.get() == "unattributed"


def test_flush_does_not_touch_database_or_repeat_empty_windows(
    counters, caplog, monkeypatch
):
    def fail(*args, **kwargs):
        pytest.fail("logging must not connect to Postgres")

    monkeypatch.setattr("app.db.session.engine.connect", fail)
    with caplog.at_level("INFO", logger=usage.__name__):
        with usage.database_source("api:GET /games"):
            usage.record_activity("game_cache_hits")
        usage.flush_usage()
        usage.flush_usage()
    assert len(summaries(caplog)) == 1
    assert summaries(caplog)[0]["sources"]["api:GET /games"]["db_minutes"] == []


def test_shutdown_flushes_partial_window_without_database_queries(caplog):
    with caplog.at_level("INFO", logger=usage.__name__):
        with usage.database_usage_logging():
            with usage.database_source("worker:competition_scan"):
                usage.record_activity("connections", database=True)
    assert (
        summaries(caplog)[0]["sources"]["worker:competition_scan"]["connections"] == 1
    )
    assert not usage._enabled
