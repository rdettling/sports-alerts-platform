"""In-memory activity counters; collecting and flushing never contacts Postgres."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Event, Lock, Thread

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)
_source: ContextVar[str | Scope] = ContextVar("database_source", default="unattributed")
_lock = Lock()
_enabled = False
_counts: dict[str, Counter] = {}
_minutes: dict[str, set[str]] = {}
_window_start = datetime.now(timezone.utc)


@contextmanager
def database_source(source: str | Scope):
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)


def record_activity(counter: str, *, database: bool = False) -> None:
    if not _enabled:
        return
    source = _source.get()
    if isinstance(source, dict):
        route = source.get("route")
        source = f"api:{source['method']} {getattr(route, 'path', 'unmatched')}"
    with _lock:
        _counts.setdefault(source, Counter())[counter] += 1
        if database:
            minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            _minutes.setdefault(source, set()).add(minute)


def flush_usage() -> None:
    global _window_start
    with _lock:
        now = datetime.now(timezone.utc)
        payload = {
            "revision": os.getenv("RENDER_GIT_COMMIT", "local"),
            "window_start": _window_start.isoformat(),
            "window_end": now.isoformat(),
            "sources": {
                source: {**counts, "db_minutes": sorted(_minutes.get(source, set()))}
                for source, counts in sorted(_counts.items())
            },
        }
        _counts.clear()
        _minutes.clear()
        _window_start = now
    if payload["sources"]:
        logger.info("Database usage %s", json.dumps(payload, separators=(",", ":")))


@contextmanager
def database_usage_logging():
    global _enabled, _window_start
    _window_start = datetime.now(timezone.utc)
    _enabled = True
    stop = Event()

    def flush_periodically():
        while not stop.wait(300):
            flush_usage()

    thread = Thread(target=flush_periodically, name="database-usage", daemon=True)
    thread.start()
    logger.info("Database usage logging started interval_seconds=300")
    try:
        yield
    finally:
        stop.set()
        thread.join()
        _enabled = False
        flush_usage()


class DatabaseUsageMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # The router fills in the matched template before any endpoint DB work.
        with database_source(scope):
            await self.app(scope, receive, send)
