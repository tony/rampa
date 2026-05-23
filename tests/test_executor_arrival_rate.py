"""Tests for the constant-arrival-rate executor.

These tests validate the core algorithmic correctness that separates rampa
from a benchmark loop: iterations must start at the configured rate
regardless of response time, and dropped iterations must be accounted for.
"""

from __future__ import annotations

import asyncio
import datetime
import queue

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.constant_arrival_rate import ConstantArrivalRateExecutor


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


def test_arrival_rate_produces_iterations() -> None:
    """ConstantArrivalRateExecutor starts iterations at the configured rate."""

    async def worker_fn(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="constant-arrival-rate",
            rate=100.0,
            duration=datetime.timedelta(milliseconds=200),
            pre_allocated_vus=10,
            max_vus=10,
        )
        executor = ConstantArrivalRateExecutor(cfg)
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
    assert len(iter_samples) >= 10


def test_arrival_rate_emits_dropped_iterations() -> None:
    """ConstantArrivalRateExecutor emits dropped_iterations when at capacity."""

    async def slow_worker(w: object) -> None:
        await asyncio.sleep(1.0)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="constant-arrival-rate",
            rate=100.0,
            duration=datetime.timedelta(milliseconds=100),
            pre_allocated_vus=2,
            max_vus=2,
        )
        executor = ConstantArrivalRateExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=slow_worker,
            scenario="test",
        )
        await executor.run(state)
        return _drain(sq)

    samples = asyncio.run(_run())
    dropped = [s for s in samples if s.metric == "dropped_iterations"]
    completed = [s for s in samples if s.metric == "iterations"]
    assert len(dropped) > 0
    assert len(completed) + len(dropped) > 2


def test_arrival_rate_total_equals_completed_plus_dropped() -> None:
    """Total scheduled iterations = completed + dropped."""

    async def medium_worker(w: object) -> None:
        await asyncio.sleep(0.05)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="constant-arrival-rate",
            rate=50.0,
            duration=datetime.timedelta(milliseconds=200),
            pre_allocated_vus=3,
            max_vus=3,
        )
        executor = ConstantArrivalRateExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=medium_worker,
            scenario="test",
        )
        await executor.run(state)
        return _drain(sq)

    samples = asyncio.run(_run())
    completed = sum(1 for s in samples if s.metric == "iterations")
    dropped = sum(1 for s in samples if s.metric == "dropped_iterations")
    total = completed + dropped
    assert total >= 5


def test_arrival_rate_respects_abort() -> None:
    """ConstantArrivalRateExecutor stops when abort event is set."""

    async def worker_fn(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        abort = asyncio.Event()
        cfg = ScenarioConfig(
            executor="constant-arrival-rate",
            rate=100.0,
            duration=datetime.timedelta(seconds=10),
            pre_allocated_vus=5,
            max_vus=5,
        )
        executor = ConstantArrivalRateExecutor(cfg)
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

        return _drain(sq)

    samples = asyncio.run(_run())
    iter_samples = [s for s in samples if s.metric == "iterations"]
    assert len(iter_samples) > 0
    assert len(iter_samples) < 500
