"""
Background scheduler loop (C1). Off by default — including in every
test — via core.config.SNAPSHOT_SCHEDULER_ENABLED: the work this loop
triggers (services.snapshot_worker.sweep_due_ideas, and C3's criteria
lapse sweep) is always directly callable and testable on its own,
regardless of whether this "run it forever, periodically" wrapper is
running. main.py's lifespan starts it when the flag is set and cancels
it on shutdown.
"""
import asyncio

from core.config import SNAPSHOT_SCHEDULER_INTERVAL_SECONDS
from core.logging import get_logger
from services import snapshot_worker

logger = get_logger("notaflop.scheduler")

_task: asyncio.Task | None = None

# C3 registers its lapse sweep here once that task lands, so this loop
# doesn't need to import a module that doesn't exist yet at C1.
_extra_sweeps: list = []


def register_sweep(coro_fn) -> None:
    """Adds an additional no-arg async callable to run on every tick,
    after the snapshot sweep. Used by C3 to add the kill-criteria lapse
    sweep without this module depending on criteria_repository at C1."""
    _extra_sweeps.append(coro_fn)


async def _tick() -> None:
    try:
        snapshots = await snapshot_worker.sweep_due_ideas()
        logger.info("scheduler_snapshot_sweep_complete", snapshots_written=len(snapshots), status="ok")
    except Exception:
        logger.error("scheduler_snapshot_sweep_failed", status="error", exc_info=True)

    for sweep in _extra_sweeps:
        try:
            await sweep()
        except Exception:
            logger.error("scheduler_extra_sweep_failed", sweep=getattr(sweep, "__name__", "?"), status="error", exc_info=True)


async def _loop() -> None:
    while True:
        await _tick()
        await asyncio.sleep(SNAPSHOT_SCHEDULER_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_loop())
    logger.info("scheduler_started", interval_s=SNAPSHOT_SCHEDULER_INTERVAL_SECONDS, status="ok")


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("scheduler_stopped", status="ok")
