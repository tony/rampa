"""Tests for the ramping-vus executor."""

from __future__ import annotations

import asyncio
import datetime
import queue

from rampa._types import Sample
from rampa.config import ScenarioConfig, Stage
from rampa.executors import ExecutionState
from rampa.executors.ramping_vus import RampingVUsExecutor


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


def test_ramping_vus_produces_iterations() -> None:
    """RampingVUsExecutor runs iterations during ramp stages."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.005)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        cfg = ScenarioConfig(
            executor="ramping-vus",
            vus=0,
            stages=[
                Stage(
                    duration=datetime.timedelta(milliseconds=100),
                    target=3,
                ),
            ],
        )
        executor = RampingVUsExecutor(cfg)
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
    assert len(iter_samples) > 0


def test_ramping_vus_respects_abort() -> None:
    """RampingVUsExecutor stops when abort event is set."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.005)

    async def _run() -> int:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        abort = asyncio.Event()
        cfg = ScenarioConfig(
            executor="ramping-vus",
            vus=2,
            stages=[
                Stage(
                    duration=datetime.timedelta(seconds=10),
                    target=5,
                ),
            ],
        )
        executor = RampingVUsExecutor(cfg)
        state = ExecutionState(
            sample_queue=sq,
            abort_event=abort,
            worker_fn=_noop,
            scenario="test",
        )

        async def _abort_after() -> None:
            await asyncio.sleep(0.15)
            abort.set()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(executor.run(state))
            tg.create_task(_abort_after())

        samples = _drain(sq)
        return sum(1 for s in samples if s.metric == "iterations")

    count = asyncio.run(_run())
    assert count > 0
    assert count < 500
