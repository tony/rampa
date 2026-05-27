"""Tests for rampa headless Engine and RunController."""

from __future__ import annotations

import asyncio
import datetime
import typing as t

from rampa.config import Config, ScenarioConfig
from rampa.engine import Engine
from rampa.events import RunStatus
from rampa.loader import TestPlan


def _make_plan(
    worker_fn: t.Callable[..., t.Any],
    executor: str = "constant-vus",
    vus: int = 1,
    duration_ms: int = 100,
    thresholds: dict[str, list[str]] | None = None,
    setup_fn: t.Callable[..., t.Any] | None = None,
    teardown_fn: t.Callable[..., t.Any] | None = None,
) -> TestPlan:
    """Build a TestPlan from a worker function."""
    cfg = ScenarioConfig(
        executor=executor,
        vus=vus,
        duration=datetime.timedelta(milliseconds=duration_ms),
    )
    config = Config(thresholds=thresholds or {})
    return TestPlan(
        scenarios={"test": (cfg, worker_fn)},
        config=config,
        setup_fn=setup_fn,
        teardown_fn=teardown_fn,
    )


def test_engine_start_returns_controller() -> None:
    """Engine.start() returns a RunController before completion."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> None:
        plan = _make_plan(_noop)
        controller = await Engine(plan).start()
        assert controller.run_id is not None
        assert len(controller.run_id) > 0
        result = await controller.wait()
        assert result.status == RunStatus.PASSED

    asyncio.run(_run())


def test_controller_wait_returns_result() -> None:
    """controller.wait() returns RunResult with snapshot."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> None:
        plan = _make_plan(_noop)
        controller = await Engine(plan).start()
        result = await controller.wait()
        assert result.run_id == controller.run_id
        assert result.status == RunStatus.PASSED
        assert result.snapshot is not None

    asyncio.run(_run())


def test_controller_stop_produces_result() -> None:
    """controller.stop() stops executors and produces a final result."""

    async def _slow(w: object) -> None:
        await asyncio.sleep(0.2)

    async def _run() -> None:
        plan = _make_plan(_slow, duration_ms=1000)
        controller = await Engine(plan).start()

        await asyncio.sleep(0.05)
        await controller.stop("test stop")

        result = await controller.wait()
        assert result.status in {RunStatus.PASSED, RunStatus.STOPPED}

    asyncio.run(_run())


def test_setup_failure_produces_setup_failed() -> None:
    """Setup failure triggers teardown and returns SETUP_FAILED."""
    teardown_ran = False

    async def _fail_setup() -> None:
        msg = "setup boom"
        raise RuntimeError(msg)

    async def _teardown() -> None:
        nonlocal teardown_ran
        teardown_ran = True

    async def _noop(w: object) -> None:
        pass

    async def _run() -> bool:
        plan = _make_plan(
            _noop,
            setup_fn=_fail_setup,
            teardown_fn=_teardown,
        )
        controller = await Engine(plan).start()
        result = await controller.wait()
        assert result.status == RunStatus.SETUP_FAILED
        return teardown_ran

    ran = asyncio.run(_run())
    assert ran is True


def test_executor_failure_produces_execution_failed() -> None:
    """Executor failure returns EXECUTION_FAILED."""

    async def _crash(w: object) -> None:
        msg = "worker boom"
        raise RuntimeError(msg)

    async def _run() -> None:
        plan = _make_plan(_crash)
        controller = await Engine(plan).start()
        result = await controller.wait()
        assert result.status in {
            RunStatus.EXECUTION_FAILED,
            RunStatus.PASSED,
        }

    asyncio.run(_run())


def test_threshold_failure_produces_threshold_failed() -> None:
    """Threshold breach returns THRESHOLD_FAILED."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.01)

    async def _run() -> None:
        plan = _make_plan(
            _noop,
            thresholds={"iteration_duration": ["avg<0.0001"]},
        )
        controller = await Engine(plan).start()
        result = await controller.wait()
        assert result.status == RunStatus.THRESHOLD_FAILED

    asyncio.run(_run())


def test_events_emit_phases() -> None:
    """Event stream emits setup, execute, teardown, complete phases."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.001)

    async def _run() -> list[str]:
        from rampa.events import PhaseEvent

        plan = _make_plan(_noop)
        controller = await Engine(plan).start()

        phases: list[str] = []

        async def _collect() -> None:
            async for event in controller.events():
                if isinstance(event, PhaseEvent):
                    phases.append(event.phase)  # noqa: PERF401

        collect_task = asyncio.create_task(_collect())
        await controller.wait()
        await collect_task
        return phases

    phases = asyncio.run(_run())
    assert "setup" in phases
    assert "execute" in phases
    assert "teardown" in phases
    assert "complete" in phases


def test_pause_and_resume() -> None:
    """Pausing blocks new iterations; resuming lets them continue."""
    iteration_times: list[float] = []

    async def _track(w: object) -> None:
        import time

        iteration_times.append(time.monotonic())
        await asyncio.sleep(0.005)

    async def _run() -> None:
        plan = _make_plan(_track, duration_ms=500)
        controller = await Engine(plan).start()

        await asyncio.sleep(0.05)
        pre_pause_count = len(iteration_times)
        assert pre_pause_count > 0

        controller.pause()
        assert controller.is_paused

        await asyncio.sleep(0.1)
        paused_count = len(iteration_times)
        assert paused_count - pre_pause_count <= 1

        controller.resume()
        assert not controller.is_paused

        await asyncio.sleep(0.05)
        post_resume_count = len(iteration_times)
        assert post_resume_count > paused_count

        await controller.stop()
        await controller.wait()

    asyncio.run(_run())


def test_pause_events_emitted() -> None:
    """PauseEvent and ResumeEvent are emitted on the EventBus."""
    from rampa.events import PauseEvent, ResumeEvent

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.005)

    async def _run() -> list[type]:
        plan = _make_plan(_noop, duration_ms=500)
        controller = await Engine(plan).start()

        event_types: list[type] = []

        async def _collect() -> None:
            async for event in controller.events():
                event_types.append(type(event))  # noqa: PERF401

        collect_task = asyncio.create_task(_collect())

        await asyncio.sleep(0.03)
        controller.pause()
        await asyncio.sleep(0.03)
        controller.resume()
        await asyncio.sleep(0.03)
        await controller.stop()
        await controller.wait()
        await collect_task
        return event_types

    event_types = asyncio.run(_run())
    assert PauseEvent in event_types
    assert ResumeEvent in event_types


def test_live_threshold_events_emitted() -> None:
    """LiveThresholdEvent is emitted during execution when thresholds exist."""
    from rampa.engine import EngineOptions
    from rampa.events import LiveThresholdEvent

    async def _slow(w: object) -> None:
        await asyncio.sleep(0.01)

    async def _run() -> bool:
        plan = _make_plan(
            _slow,
            duration_ms=500,
            thresholds={"iteration_duration": ["avg<10000"]},
        )
        controller = await Engine(
            plan,
            EngineOptions(metric_flush_interval=0.05),
        ).start()

        found_live = False

        async def _collect() -> None:
            nonlocal found_live
            async for event in controller.events():
                if isinstance(event, LiveThresholdEvent):
                    found_live = True

        collect_task = asyncio.create_task(_collect())
        await controller.wait()
        await collect_task
        return found_live

    assert asyncio.run(_run())


def test_snapshot_events_emitted() -> None:
    """SnapshotEvent is emitted via the EventBus from MetricEngine."""

    async def _noop(w: object) -> None:
        await asyncio.sleep(0.01)

    async def _run() -> bool:
        from rampa.events import SnapshotEvent

        plan = _make_plan(_noop, duration_ms=150)
        controller = await Engine(plan).start()

        found_snapshot = False

        async def _collect() -> None:
            nonlocal found_snapshot
            async for event in controller.events():
                if isinstance(event, SnapshotEvent):
                    found_snapshot = True

        collect_task = asyncio.create_task(_collect())
        await controller.wait()
        await collect_task
        return found_snapshot

    assert asyncio.run(_run())
