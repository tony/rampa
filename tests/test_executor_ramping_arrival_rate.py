"""Tests for the ramping-arrival-rate executor."""

from __future__ import annotations

import asyncio
import datetime
import queue

from rampa._types import Sample
from rampa.config import ScenarioConfig, Stage
from rampa.executors import ExecutionState
from rampa.executors.ramping_arrival_rate import RampingArrivalRateExecutor


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


def test_ramping_arrival_rate_produces_iterations() -> None:
    """RampingArrivalRateExecutor starts iterations during ramp stages."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="ramping-arrival-rate",
            rate=50.0,
            stages=[
                Stage(
                    duration=datetime.timedelta(milliseconds=200),
                    target=100,
                ),
            ],
            max_vus=10,
        )
        executor = RampingArrivalRateExecutor(cfg)
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
    assert len(iter_samples) >= 5


def test_ramping_arrival_rate_emits_dropped() -> None:
    """RampingArrivalRateExecutor emits dropped_iterations at capacity."""

    async def _slow(w: object) -> None:
        await asyncio.sleep(1.0)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="ramping-arrival-rate",
            rate=100.0,
            stages=[
                Stage(
                    duration=datetime.timedelta(milliseconds=100),
                    target=200,
                ),
            ],
            max_vus=2,
        )
        executor = RampingArrivalRateExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=_slow,
            scenario="test",
        )
        await executor.run(state)
        return _drain(sq)

    samples = asyncio.run(_run())
    dropped = [s for s in samples if s.metric == "dropped_iterations"]
    assert len(dropped) > 0


def test_ramping_arrival_rate_respects_abort() -> None:
    """RampingArrivalRateExecutor stops when abort event is set."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> int:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        abort = asyncio.Event()
        cfg = ScenarioConfig(
            executor="ramping-arrival-rate",
            rate=50.0,
            stages=[
                Stage(
                    duration=datetime.timedelta(seconds=10),
                    target=100,
                ),
            ],
            max_vus=5,
        )
        executor = RampingArrivalRateExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=abort,
            worker_fn=_noop,
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
    assert count < 500
