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
from rampa.events import (
    EngineEvent,
    PhaseEvent,
    RunResult,
    RunStatus,
    ThresholdEvent,
)
from rampa.executors import ExecutionState, create_executor
from rampa.loader import TestPlan
from rampa.metrics import MetricEngine, MetricRegistry, MetricSnapshot, register_builtins
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
        event_queue: asyncio.Queue[EngineEvent | None],
    ) -> None:
        self._run_id = run_id
        self._run_task = run_task
        self._abort_event = abort_event
        self._metric_engine = metric_engine
        self._event_queue = event_queue
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

    def snapshot(self) -> MetricSnapshot | None:
        """Return the latest metric snapshot, or None if none emitted."""
        return self._metric_engine.get_latest_snapshot()

    async def events(self) -> t.AsyncIterator[EngineEvent]:
        """Single-consumer async iterator of engine events.

        Yields
        ------
        EngineEvent
            Engine lifecycle events until the run completes.
        """
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
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

        metric_engine = MetricEngine(
            registry=registry,
            sample_queue=sample_queue,
            flush_interval=self._options.metric_flush_interval,
            on_sample=self._options.on_sample,
        )
        metric_engine.start()

        abort_event = asyncio.Event()
        event_queue: asyncio.Queue[EngineEvent | None] = asyncio.Queue()

        run_task = asyncio.create_task(
            self._run(
                run_id=run_id,
                registry=registry,
                sample_queue=sample_queue,
                metric_engine=metric_engine,
                abort_event=abort_event,
                event_queue=event_queue,
            ),
        )

        return RunController(
            run_id=run_id,
            run_task=run_task,
            abort_event=abort_event,
            metric_engine=metric_engine,
            event_queue=event_queue,
        )

    async def _run(
        self,
        run_id: str,
        registry: MetricRegistry,
        sample_queue: queue.SimpleQueue[Sample | None],
        metric_engine: MetricEngine,
        abort_event: asyncio.Event,
        event_queue: asyncio.Queue[EngineEvent | None],
    ) -> RunResult:
        """Execute the full lifecycle: setup → execute → teardown."""
        status = RunStatus.PASSED
        error: BaseException | None = None
        stop_reason: str | None = None

        def _emit(event: EngineEvent) -> None:
            event_queue.put_nowait(event)

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
            metric_engine.stop()
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
            event_queue.put_nowait(None)

        return RunResult(
            run_id=run_id,
            status=status,
            snapshot=snapshot,
            threshold_results=threshold_results,
            error=error,
            stop_reason=stop_reason,
        )
