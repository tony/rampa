"""Headless engine and run controller for rampa.

The engine owns execution state and cleanup. Frontends own presentation,
JSON shape, and process exit behavior. This separation enables CLI, TUI,
MCP, pytest, and GitHub Action integration without reaching into internals.

>>> import rampa.engine
"""

from __future__ import annotations

import asyncio
import logging
import queue
import signal
import sys
import threading
import time
import typing as t
import uuid
from dataclasses import dataclass

import rampa.executors.constant_arrival_rate as _car  # noqa: F401
import rampa.executors.constant_vus as _cv  # noqa: F401
import rampa.executors.per_vu_iterations as _pvi  # noqa: F401
import rampa.executors.ramping_arrival_rate as _rar  # noqa: F401
import rampa.executors.ramping_vus as _rv  # noqa: F401
import rampa.executors.shared_iterations as _si  # noqa: F401
from rampa._types import Sample
from rampa.bus import EventBus
from rampa.events import (
    EngineEvent,
    PhaseEvent,
    RunResult,
    RunStatus,
    SnapshotEvent,
    ThresholdEvent,
)
from rampa.executors import ExecutionState, create_executor
from rampa.loader import TestPlan
from rampa.metrics import MetricEngine, MetricRegistry, MetricSnapshot, register_builtins
from rampa.pause import PauseController
from rampa.thresholds import Threshold, evaluate_thresholds, parse_threshold

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineOptions:
    """Configuration for engine behavior.

    >>> opts = EngineOptions()
    >>> opts.metric_flush_interval
    0.05
    """

    run_id: str | None = None
    metric_flush_interval: float = 0.05
    on_sample: t.Callable[[Sample], None] | None = None


class RunController:
    """Control surface for a running test.

    Returned by ``Engine.start()``. Provides ``wait()``, ``stop()``,
    ``snapshot()``, and ``events()`` for frontend consumption.

    >>> import rampa.engine
    """

    def __init__(
        self,
        run_id: str,
        run_task: asyncio.Task[RunResult],
        abort_event: asyncio.Event,
        metric_engine: MetricEngine,
        bus: EventBus,
        primary_queue: asyncio.Queue[EngineEvent | None],
        pause_controller: PauseController,
    ) -> None:
        self._run_id = run_id
        self._run_task = run_task
        self._abort_event = abort_event
        self._metric_engine = metric_engine
        self._bus = bus
        self._primary_queue = primary_queue
        self._pause_controller = pause_controller
        self._stopped = False

    @property
    def run_id(self) -> str:
        """Return the unique run identifier."""
        return self._run_id

    async def wait(self) -> RunResult:
        """Await the run task and return the final result.

        Returns
        -------
        RunResult
            The headless run result with status, snapshot, and thresholds.
        """
        return await self._run_task

    async def stop(self, reason: str | None = None) -> None:
        """Request graceful stop.

        Idempotent — safe to call multiple times.

        Parameters
        ----------
        reason : str | None
            Optional reason for stopping.
        """
        if not self._stopped:
            self._stopped = True
            self._abort_event.set()
            logger.info("stop requested: %s", reason or "no reason given")

    def pause(self) -> None:
        """Pause execution.

        Executors will block before their next iteration until
        ``resume()`` is called. Idempotent.
        """
        from rampa.events import PauseEvent

        self._pause_controller.pause()
        self._bus.publish(
            PauseEvent(
                run_id=self._run_id,
                timestamp_ns=time.monotonic_ns(),
            ),
        )
        logger.info("execution paused")

    def resume(self) -> None:
        """Resume execution after a pause. Idempotent."""
        from rampa.events import ResumeEvent

        paused = self._pause_controller.total_paused_seconds
        self._pause_controller.resume()
        self._bus.publish(
            ResumeEvent(
                run_id=self._run_id,
                timestamp_ns=time.monotonic_ns(),
                paused_seconds=paused,
            ),
        )
        logger.info("execution resumed (paused %.2fs)", paused)

    @property
    def is_paused(self) -> bool:
        """Return whether execution is currently paused."""
        return self._pause_controller.is_paused

    def snapshot(self) -> MetricSnapshot | None:
        """Return the latest metric snapshot, or None if none emitted."""
        return self._metric_engine.get_latest_snapshot()

    async def events(self) -> t.AsyncIterator[EngineEvent]:
        """Async iterator of engine events.

        The first caller drains the primary queue that was subscribed
        before the engine task started — this guarantees no early
        events are lost. Additional callers subscribe independently
        via the EventBus (they may miss events emitted before they
        subscribe).

        Yields
        ------
        EngineEvent
            Engine lifecycle events until the run completes.
        """
        q = self._primary_queue
        if q is not None:
            self._primary_queue = None  # type: ignore[assignment]
            try:
                while True:
                    event = await q.get()
                    if event is None:
                        break
                    yield event
            finally:
                self._bus.unsubscribe(q)
        else:
            async for event in self._bus.events():
                yield event


class Engine:
    """Headless load testing engine.

    Constructs per-run state, starts scenarios, and returns a controller.

    Parameters
    ----------
    plan : TestPlan
        Resolved test plan from the loader.
    options : EngineOptions | None
        Optional engine configuration.

    >>> import rampa.engine
    """

    def __init__(
        self,
        plan: TestPlan,
        options: EngineOptions | None = None,
    ) -> None:
        self._plan = plan
        self._options = options or EngineOptions()

    async def start(self) -> RunController:
        """Start the engine and return a run controller.

        Returns
        -------
        RunController
            Control surface for the running test.
        """
        run_id = self._options.run_id or uuid.uuid4().hex[:12]

        registry = MetricRegistry()
        register_builtins(registry)

        sample_queue: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()

        loop = asyncio.get_running_loop()
        bus = EventBus(loop)

        def _bridge_snapshot(snap: MetricSnapshot) -> None:
            bus.publish_threadsafe(
                SnapshotEvent(
                    run_id=run_id,
                    timestamp_ns=snap.timestamp,
                    snapshot=snap,
                ),
            )

        abort_event = asyncio.Event()

        from rampa.thresholds import parse_submetric

        live_thresholds: dict[str, list[Threshold]] | None = None
        if self._plan.config.thresholds:
            live_thresholds = {}
            for metric_name, expressions in self._plan.config.thresholds.items():
                _base, tag_filter = parse_submetric(metric_name)
                if tag_filter:
                    registry.get_or_create_sub_sink(_base, tag_filter)
                live_thresholds[metric_name] = [
                    Threshold(
                        source=expr,
                        expression=parse_threshold(expr),
                    )
                    if isinstance(expr, str)
                    else expr
                    for expr in expressions
                ]

        def _bridge_threshold(results: list[t.Any]) -> None:
            from rampa.events import LiveThresholdEvent

            bus.publish_threadsafe(
                LiveThresholdEvent(
                    run_id=run_id,
                    timestamp_ns=time.monotonic_ns(),
                    results=results,
                    will_abort=any(not r.passed for r in results if hasattr(r, "passed")),
                ),
            )

        metric_engine = MetricEngine(
            registry=registry,
            sample_queue=sample_queue,
            flush_interval=self._options.metric_flush_interval,
            on_sample=self._options.on_sample,
            on_snapshot=_bridge_snapshot,
            thresholds=live_thresholds or {},
            on_threshold=_bridge_threshold if live_thresholds else None,
            abort_callback=abort_event.set if live_thresholds else None,
        )
        metric_engine.start()
        pause_controller = PauseController()

        installed_signals: list[int] = []
        if sys.platform != "win32" and threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, abort_event.set)
                installed_signals.append(sig)

        primary_queue = bus.subscribe()

        run_task = asyncio.create_task(
            self._run(
                run_id=run_id,
                registry=registry,
                sample_queue=sample_queue,
                metric_engine=metric_engine,
                abort_event=abort_event,
                bus=bus,
                installed_signals=installed_signals,
                pause_controller=pause_controller,
            ),
        )

        return RunController(
            run_id=run_id,
            run_task=run_task,
            abort_event=abort_event,
            metric_engine=metric_engine,
            bus=bus,
            primary_queue=primary_queue,
            pause_controller=pause_controller,
        )

    async def _run(
        self,
        run_id: str,
        registry: MetricRegistry,
        sample_queue: queue.SimpleQueue[Sample | None],
        metric_engine: MetricEngine,
        abort_event: asyncio.Event,
        bus: EventBus,
        installed_signals: list[int] | None = None,
        pause_controller: PauseController | None = None,
    ) -> RunResult:
        """Execute the full lifecycle: setup → execute → teardown."""
        status = RunStatus.PASSED
        error: BaseException | None = None
        stop_reason: str | None = None

        def _emit(event: EngineEvent) -> None:
            bus.publish(event)

        def _phase(
            phase: t.Literal["setup", "execute", "teardown", "complete"],
        ) -> None:
            _emit(
                PhaseEvent(
                    run_id=run_id,
                    timestamp_ns=time.monotonic_ns(),
                    phase=phase,
                )
            )

        from rampa.context import run_id_var

        run_id_var.set(run_id)

        try:
            setup_data: t.Any = None

            _phase("setup")
            try:
                if self._plan.setup_fn is not None:
                    setup_data = await self._plan.setup_fn()
            except Exception as exc:
                logger.exception("setup failed")
                status = RunStatus.SETUP_FAILED
                error = exc

            if status == RunStatus.PASSED:
                _phase("execute")
                try:
                    async with asyncio.TaskGroup() as tg:
                        for name, (cfg, fn) in self._plan.scenarios.items():
                            executor = create_executor(cfg)
                            state = ExecutionState(
                                sample_queue=sample_queue,
                                abort_event=abort_event,
                                worker_fn=fn,
                                scenario=name,
                                setup_data=setup_data,
                                pause_controller=pause_controller or PauseController(),
                            )
                            tg.create_task(executor.run(state))
                except Exception as exc:
                    logger.exception("executor error")
                    status = RunStatus.EXECUTION_FAILED
                    error = exc

            _phase("teardown")
            if self._plan.teardown_fn is not None:
                try:
                    await self._plan.teardown_fn()
                except Exception as exc:
                    logger.exception("teardown failed")
                    if status == RunStatus.PASSED:
                        status = RunStatus.TEARDOWN_FAILED
                        error = exc

        finally:
            if installed_signals and sys.platform != "win32":
                loop = asyncio.get_running_loop()
                for sig in installed_signals:
                    loop.remove_signal_handler(sig)

            metric_engine.stop()
            await asyncio.sleep(0)
            snapshot = metric_engine.get_latest_snapshot()

            threshold_results = []
            if snapshot and self._plan.config.thresholds:
                metric_thresholds: dict[str, list[Threshold]] = {}
                for metric_name, expressions in self._plan.config.thresholds.items():
                    metric_thresholds[metric_name] = [
                        Threshold(
                            source=expr,
                            expression=parse_threshold(expr),
                        )
                        for expr in expressions
                    ]
                threshold_results = evaluate_thresholds(
                    metric_thresholds,
                    registry.all_sinks(),
                    snapshot.duration,
                    sub_sinks=registry.all_sub_sinks(),
                )

                if threshold_results:
                    _emit(
                        ThresholdEvent(
                            run_id=run_id,
                            timestamp_ns=time.monotonic_ns(),
                            results=threshold_results,
                        )
                    )

                if any(not r.passed for r in threshold_results) and status == RunStatus.PASSED:
                    status = RunStatus.THRESHOLD_FAILED

            if abort_event.is_set() and status == RunStatus.PASSED:
                status = RunStatus.STOPPED
                stop_reason = "abort requested"

            _phase("complete")
            bus.publish(None)

        return RunResult(
            run_id=run_id,
            status=status,
            snapshot=snapshot,
            threshold_results=threshold_results,
            error=error,
            stop_reason=stop_reason,
        )
