"""Tests for the constant-vus executor and create_executor factory."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import queue
import typing as t

import pytest

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState, create_executor
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


# ---------------------------------------------------------------------------
# create_executor factory tests
# ---------------------------------------------------------------------------


class UnknownExecutorFixture(t.NamedTuple):
    """Test case for unknown executor error messages."""

    test_id: str
    name: str
    expected_suggestion: str | None


_UNKNOWN_EXECUTOR_FIXTURES: list[UnknownExecutorFixture] = [
    UnknownExecutorFixture(
        test_id="typo_constant",
        name="contsant-vus",
        expected_suggestion="constant-vus",
    ),
    UnknownExecutorFixture(
        test_id="typo_ramping",
        name="rampng-vus",
        expected_suggestion="ramping-vus",
    ),
    UnknownExecutorFixture(
        test_id="no_match",
        name="nonexistent-executor",
        expected_suggestion=None,
    ),
]


@pytest.mark.parametrize(
    list(UnknownExecutorFixture._fields),
    _UNKNOWN_EXECUTOR_FIXTURES,
    ids=[f.test_id for f in _UNKNOWN_EXECUTOR_FIXTURES],
)
def test_create_executor_unknown_suggests(
    test_id: str,
    name: str,
    expected_suggestion: str | None,
) -> None:
    """create_executor suggests close matches for unknown executor names."""
    cfg = ScenarioConfig(executor=name)
    with pytest.raises(ValueError, match="unknown executor"):
        create_executor(cfg)

    try:
        create_executor(cfg)
    except ValueError as exc:
        msg = str(exc)
        if expected_suggestion:
            assert f"did you mean {expected_suggestion!r}" in msg
        else:
            assert "did you mean" not in msg


def test_create_executor_valid() -> None:
    """create_executor returns an executor for a valid name."""
    cfg = ScenarioConfig(
        executor="constant-vus",
        vus=1,
        duration=datetime.timedelta(seconds=1),
    )
    executor = create_executor(cfg)
    assert isinstance(executor, ConstantVUsExecutor)


def test_cancelled_iteration_still_emits_metrics() -> None:
    """Iteration metrics are emitted even when CancelledError propagates."""
    from rampa.executors import run_iteration

    async def _slow(w: object) -> None:
        await asyncio.sleep(10.0)

    async def _run() -> list[Sample]:
        sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
        state = ExecutionState(
            sample_queue=sq,
            abort_event=asyncio.Event(),
            worker_fn=_slow,
            scenario="test",
        )

        task = asyncio.create_task(run_iteration(state))
        await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        return _drain(sq)

    samples = asyncio.run(_run())
    metrics = [s.metric for s in samples]
    assert "iterations" in metrics
    assert "iteration_duration" in metrics
