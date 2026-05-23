"""Tests for the per-vu-iterations executor."""

from __future__ import annotations

import asyncio
import queue

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.per_vu_iterations import PerVUIterationsExecutor


def _drain(sq: queue.SimpleQueue[Sample | None]) -> list[Sample]:
    """Drain all samples from a queue."""
    samples: list[Sample] = []
    while True:
        try:
            s = sq.get_nowait()
        except Exception:
            break
        if s is not None:
            samples.append(s)
    return samples


def test_per_vu_iterations_count() -> None:
    """PerVUIterationsExecutor runs VUs * iterations total."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="per-vu-iterations",
            vus=3,
            iterations=5,
        )
        executor = PerVUIterationsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=_noop,
            scenario="test",
        )
        await executor.run(state)
        return _drain(sq)

    samples = asyncio.run(_run())
    iter_samples = [s for s in samples if s.metric == "iterations"]
    assert len(iter_samples) == 15


def test_per_vu_iterations_respects_abort() -> None:
    """PerVUIterationsExecutor stops when abort event is set."""

    async def _slow(w: object) -> None:
        await asyncio.sleep(0.01)

    async def _run() -> int:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        abort = asyncio.Event()
        cfg = ScenarioConfig(
            executor="per-vu-iterations",
            vus=2,
            iterations=500,
        )
        executor = PerVUIterationsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=abort,
            worker_fn=_slow,
            scenario="test",
        )

        async def _abort_after() -> None:
            await asyncio.sleep(0.05)
            abort.set()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(executor.run(state))
            tg.create_task(_abort_after())

        samples = _drain(sq)
        return sum(1 for s in samples if s.metric == "iterations")

    count = asyncio.run(_run())
    assert count > 0
    assert count < 1000
