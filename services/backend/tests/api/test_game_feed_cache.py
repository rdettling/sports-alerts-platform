from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event

from app.db.session import engine
from app.services import game_feed


def test_cache_hits_do_not_open_connections_and_expiry_does_not_slide(monkeypatch):
    now = 100.0
    calls = []

    def load(db, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(game_feed, "monotonic", lambda: now)
    monkeypatch.setattr(game_feed, "load_games", load)
    cache = game_feed.GameFeedCache()
    first = cache.get()
    now = 129.0

    def unexpected_checkout(*args):
        pytest.fail("cache hit must not check out a database connection")

    event.listen(engine, "checkout", unexpected_checkout)
    try:
        assert cache.get() is first
    finally:
        event.remove(engine, "checkout", unexpected_checkout)
    now = 130.0
    assert cache.get() is not first
    assert calls == [{"include_finals": True, "limit": 500}] * 2


def test_concurrent_misses_share_one_fill(monkeypatch):
    entered = Event()
    release = Event()
    calls = []
    games = []

    def load(db, **kwargs):
        calls.append(db)
        entered.set()
        assert release.wait(2)
        return games

    monkeypatch.setattr(game_feed, "load_games", load)
    cache = game_feed.GameFeedCache()
    with ThreadPoolExecutor(max_workers=4) as executor:
        first = executor.submit(cache.get)
        assert entered.wait(2)
        rest = [executor.submit(cache.get) for _ in range(3)]
        release.set()
        assert all(future.result(timeout=2) is games for future in [first, *rest])
    assert len(calls) == 1


def test_invalidation_during_fill_is_nonblocking_and_discards_old_result(monkeypatch):
    entered = Event()
    release = Event()
    sessions = []
    old_games, new_games = [], []

    def load(db, **kwargs):
        sessions.append(db)
        if len(sessions) == 1:
            entered.set()
            assert release.wait(2)
            return old_games
        return new_games

    monkeypatch.setattr(game_feed, "load_games", load)
    cache = game_feed.GameFeedCache()
    with ThreadPoolExecutor(max_workers=2) as executor:
        fill = executor.submit(cache.get)
        assert entered.wait(2)
        try:
            executor.submit(cache.invalidate).result(timeout=1)
        finally:
            release.set()
        assert fill.result(timeout=2) is new_games
    assert cache.get() is new_games
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]


def test_expired_cache_does_not_serve_stale_data_or_cache_errors(monkeypatch):
    now = 0.0
    monkeypatch.setattr(game_feed, "monotonic", lambda: now)
    monkeypatch.setattr(game_feed, "load_games", lambda db, **kwargs: [])
    cache = game_feed.GameFeedCache()
    first = cache.get()
    now = 31.0

    def fail(db, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(game_feed, "load_games", fail)
    with pytest.raises(RuntimeError, match="database unavailable"):
        cache.get()
    monkeypatch.setattr(game_feed, "load_games", lambda db, **kwargs: [])
    assert cache.get() is not first
