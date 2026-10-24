import asyncio
import threading

import pytest

from app.worker import runtime, updates


def test_runtime_joins_both_threads_and_can_restart(monkeypatch):
    started = []

    def wait_for_shutdown(stop, wake):
        started.append(threading.current_thread().name)
        stop.wait()

    monkeypatch.setattr(runtime.scheduler, "run", wait_for_shutdown)
    monkeypatch.setattr(runtime, "run_delivery_loop", wait_for_shutdown)

    async def scenario():
        async with runtime.running_worker() as threads:
            assert all(thread.is_alive() for thread in threads)
            assert updates.event_loop is asyncio.get_running_loop()
        assert not any(thread.is_alive() for thread in threads)
        assert updates.event_loop is None
        async with runtime.running_worker():
            pass

    asyncio.run(scenario())
    assert sorted(started) == [
        "alert-delivery",
        "alert-delivery",
        "game-sync",
        "game-sync",
    ]


def test_runtime_cleans_up_if_starting_delivery_thread_fails(monkeypatch):
    started = threading.Event()
    stopped = threading.Event()
    original_start = threading.Thread.start

    def scheduler_loop(stop, wake):
        started.set()
        stop.wait()
        stopped.set()

    def start(thread):
        if thread.name == "alert-delivery":
            raise RuntimeError("Unable to start delivery")
        original_start(thread)

    monkeypatch.setattr(runtime.scheduler, "run", scheduler_loop)
    monkeypatch.setattr(threading.Thread, "start", start)

    async def scenario():
        with pytest.raises(RuntimeError, match="Unable to start delivery"):
            async with runtime.running_worker():
                pytest.fail("Startup should fail")
        assert started.is_set() and stopped.is_set()
        assert updates.event_loop is None

    asyncio.run(scenario())
