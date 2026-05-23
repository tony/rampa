"""Test runner — orchestrates the full load test lifecycle.

Sequence: setup → execute scenarios → teardown → summary.

>>> import rampa.runner
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import typing as t
from dataclasses import dataclass

import rampa.executors.constant_arrival_rate as _car  # noqa: F401
import rampa.executors.constant_vus as _cv  # noqa: F401
import rampa.executors.per_vu_iterations as _pvi  # noqa: F401
import rampa.executors.ramping_arrival_rate as _rar  # noqa: F401
import rampa.executors.ramping_vus as _rv  # noqa: F401
import rampa.executors.shared_iterations as _si  # noqa: F401
from rampa._types import Sample
from rampa.errors import ExitCode
from rampa.executors import ExecutionState, create_executor
from rampa.loader import TestPlan
from rampa.metrics import MetricEngine, MetricRegistry, register_builtins
from rampa.output import ConsoleOutput, JSONOutput, OutputManager
from rampa.thresholds import Threshold, ThresholdResult, evaluate_thresholds, parse_threshold


@dataclass(frozen=True)
class RunResult:
    """Result of a test run.

    >>> r = RunResult(exit_code=ExitCode.OK, threshold_results=[])
    >>> r.exit_code
    <ExitCode.OK: 0>
    """

    exit_code: ExitCode
    threshold_results: list[ThresholdResult]


async def run_test(
    plan: TestPlan,
    json_output_path: str | None = None,
    quiet: bool = False,
) -> RunResult:
    """Execute a test plan through the full lifecycle.

    Parameters
    ----------
    plan : TestPlan
        Resolved test plan from the loader.
    json_output_path : str | None
        Path for JSON output file. None disables JSON output.
    quiet : bool
        Suppress console summary.

    Returns
    -------
    RunResult
        The test result with exit code and threshold results.
    """
    registry = MetricRegistry()
    register_builtins(registry)

    sample_queue: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    output_samples: list[Sample] = []

    engine = MetricEngine(
        registry=registry,
        sample_queue=sample_queue,
        on_sample=output_samples.append,
    )
    engine.start()

    output_mgr = OutputManager()
    console = ConsoleOutput() if not quiet else None
    if console:
        output_mgr.add(console)

    json_out: JSONOutput | None = None
    if json_output_path:
        json_out = JSONOutput(json_output_path)
        output_mgr.add(json_out)

    await output_mgr.start_all()

    abort_event = asyncio.Event()
    setup_data: t.Any = None

    try:
        if plan.setup_fn is not None:
            setup_data = await plan.setup_fn()

        async with asyncio.TaskGroup() as tg:
            for scenario_name, (scenario_config, worker_fn) in plan.scenarios.items():
                executor = create_executor(scenario_config)

                state = ExecutionState(
                    sample_queue=sample_queue,
                    abort_event=abort_event,
                    worker_fn=worker_fn,
                    scenario=scenario_name,
                    setup_data=setup_data,
                )
                tg.create_task(executor.run(state))

    except Exception:
        import logging

        logging.getLogger(__name__).exception("executor error")

    if plan.teardown_fn is not None:
        with contextlib.suppress(Exception):
            await plan.teardown_fn()

    engine.stop()

    output_mgr.buffer_samples(output_samples)
    await output_mgr.flush()

    snapshot = engine.get_latest_snapshot()
    threshold_results: list[ThresholdResult] = []

    if snapshot and plan.config.thresholds:
        metric_thresholds: dict[str, list[Threshold]] = {}
        for metric_name, expressions in plan.config.thresholds.items():
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

    await output_mgr.stop_all()

    if snapshot:
        if console:
            console.render_summary(snapshot, threshold_results)
        if json_out:
            json_out.write_summary(snapshot, threshold_results)

    any_failed = any(not r.passed for r in threshold_results)
    exit_code = ExitCode.THRESHOLD_FAILURE if any_failed else ExitCode.OK

    return RunResult(exit_code=exit_code, threshold_results=threshold_results)
