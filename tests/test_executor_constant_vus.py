"""Tests for the constant-vus executor."""

from __future__ import annotations

import asyncio
import datetime
import queue

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.constant_vus import ConstantVUsExecutor


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


def test_constant_vus_runs_correct_number_of_vus() -> None:
    """ConstantVUsExecutor runs the configured number of VUs."""
    vus_seen: set[int] = set()

    async def worker_fn(w: object) -> None:
        from rampa.worker import Worker

        assert isinstance(w, Worker)
        vus_seen.add(w.execution.worker_id)
        await asyncio.sleep(0.01)

    async def _run() -> None:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="constant-vus",
            vus=3,
            duration=datetime.timedelta(milliseconds=100),
        )
        executor = ConstantVUsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=worker_fn,
            scenario="test",
        )
        await executor.run(state)

    asyncio.run(_run())
    assert len(vus_seen) >= 3


def test_constant_vus_emits_iteration_metrics() -> None:
    """ConstantVUsExecutor emits iterations and iteration_duration."""
    iteration_count = 0

    async def worker_fn(w: object) -> None:
        nonlocal iteration_count
        iteration_count += 1
        await asyncio.sleep(0.01)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="constant-vus",
            vus=1,
            duration=datetime.timedelta(milliseconds=100),
        )
        executor = ConstantVUsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=worker_fn,
            scenario="test",
        )
        await executor.run(state)
        return _drain(sq)

    samples = asyncio.run(_run())
    iter_samples = [s for s in samples if s.metric == "iterations"]
    dur_samples = [s for s in samples if s.metric == "iteration_duration"]
    assert len(iter_samples) > 0
    assert len(dur_samples) > 0
    assert len(iter_samples) == len(dur_samples)


def test_constant_vus_respects_abort() -> None:
    """ConstantVUsExecutor stops when abort event is set."""
    iteration_count = 0

    async def worker_fn(w: object) -> None:
        nonlocal iteration_count
        iteration_count += 1
        await asyncio.sleep(0.01)

    async def _run() -> int:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        abort = asyncio.Event()
        cfg = ScenarioConfig(
            executor="constant-vus",
            vus=1,
            duration=datetime.timedelta(seconds=10),
        )
        executor = ConstantVUsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=abort,
            worker_fn=worker_fn,
            scenario="test",
        )

        async def _abort_after() -> None:
            await asyncio.sleep(0.05)
            abort.set()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(executor.run(state))
            tg.create_task(_abort_after())

        return iteration_count

    count = asyncio.run(_run())
    assert count > 0
    assert count < 100
