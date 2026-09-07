import asyncio

import pytest

from services import scheduler


@pytest.fixture(autouse=True)
def _reset_scheduler_state():
    scheduler._task = None
    scheduler._extra_sweeps.clear()
    yield
    scheduler._task = None
    scheduler._extra_sweeps.clear()


async def test_tick_calls_snapshot_sweep_and_extra_sweeps(monkeypatch):
    from services import snapshot_worker

    calls = []

    async def _fake_sweep():
        calls.append("snapshot")
        return []

    monkeypatch.setattr(snapshot_worker, "sweep_due_ideas", _fake_sweep)

    extra_calls = []

    async def _extra():
        extra_calls.append(True)

    scheduler.register_sweep(_extra)

    await scheduler._tick()
    assert calls == ["snapshot"]
    assert extra_calls == [True]


async def test_tick_survives_sweep_failure(monkeypatch):
    from services import snapshot_worker

    async def _boom():
        raise RuntimeError("data source down")

    monkeypatch.setattr(snapshot_worker, "sweep_due_ideas", _boom)

    await scheduler._tick()  # must not raise


async def test_start_is_idempotent_and_stop_cancels(monkeypatch):
    from services import snapshot_worker

    async def _fake_sweep():
        return []

    monkeypatch.setattr(snapshot_worker, "sweep_due_ideas", _fake_sweep)
    monkeypatch.setattr("core.config.SNAPSHOT_SCHEDULER_INTERVAL_SECONDS", 3600)
    monkeypatch.setattr(scheduler, "SNAPSHOT_SCHEDULER_INTERVAL_SECONDS", 3600)

    scheduler.start()
    first_task = scheduler._task
    scheduler.start()  # second call is a no-op
    assert scheduler._task is first_task

    await scheduler.stop()
    assert scheduler._task is None
    await asyncio.sleep(0)  # let the cancellation settle
