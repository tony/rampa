"""Test runner — compatibility wrapper over the headless engine.

This module preserves the ``run_test()`` API for the CLI while delegating
to ``Engine``/``RunController`` internally.

>>> import rampa.runner
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import typing as t

from rampa.engine import Engine, EngineOptions, RunController
from rampa.errors import ExitCode
from rampa.events import RunResult, RunStatus, serialize_event
from rampa.loader import TestPlan
from rampa.metrics import MetricSnapshot
from rampa.output import ConsoleOutput, JSONOutput, OutputManager
from rampa.thresholds import ThresholdResult

logger = logging.getLogger(__name__)

_STATUS_TO_EXIT: dict[RunStatus, ExitCode] = {
    RunStatus.PASSED: ExitCode.OK,
    RunStatus.THRESHOLD_FAILED: ExitCode.THRESHOLD_FAILURE,
    RunStatus.SETUP_FAILED: ExitCode.SETUP_FAILURE,
    RunStatus.EXECUTION_FAILED: ExitCode.ITERATION_EXCEPTION,
    RunStatus.TEARDOWN_FAILED: ExitCode.TEARDOWN_FAILURE,
    RunStatus.STOPPED: ExitCode.ABORTED,
}


@t.runtime_checkable
class _SummaryOutput(t.Protocol):
    """Output backend that can render a final run summary."""

    def write_summary(
        self,
        snapshot: MetricSnapshot,
        threshold_results: list[ThresholdResult] | None = None,
    ) -> None:
        """Write a final summary from the completed run result."""
        ...


async def run_test(
    plan: TestPlan,
    json_output_path: str | None = None,
    quiet: bool = False,
    event_log_path: str | None = None,
    extra_outputs: list[t.Any] | None = None,
    progress: bool = False,
) -> RunResult:
    """Execute a test plan through the full lifecycle.

    This is a convenience wrapper that uses the headless ``Engine`` and
    adds CLI-specific output (console summary, JSON file, exit codes).

    Parameters
    ----------
    plan : TestPlan
        Resolved test plan from the loader.
    json_output_path : str | None
        Path for JSON output file. None disables JSON output.
    quiet : bool
        Suppress console summary.
    event_log_path : str | None
        Path for JSONL event log. None disables event logging.
    extra_outputs : list[Any] | None
        Additional output backends from ``--output`` flags.

    Returns
    -------
    RunResult
        The test result with status, snapshot, and threshold results.

    >>> import rampa.runner
    """
    from rampa._types import Sample

    output_samples: list[Sample] = []
    options = EngineOptions(on_sample=output_samples.append)
    controller = await Engine(plan, options).start()

    drain_task: asyncio.Task[None] | None = None
    if event_log_path:
        drain_task = asyncio.create_task(
            _drain_events(controller, event_log_path),
        )

    output_mgr = OutputManager()
    console = ConsoleOutput() if not quiet else None
    if console:
        output_mgr.add(console)

    if json_output_path:
        output_mgr.add(JSONOutput(json_output_path))

    if extra_outputs:
        for out in extra_outputs:
            output_mgr.add(out)

    await output_mgr.start_all()

    progress_task: asyncio.Task[None] | None = None
    if progress:
        progress_task = asyncio.create_task(
            _progress_loop(controller),
        )

    result = await controller.wait()

    if progress_task is not None:
        progress_task.cancel()
        from rampa.cli._progress import clear_progress

        clear_progress()

    if drain_task is not None:
        await drain_task

    output_mgr.buffer_samples(output_samples)
    await output_mgr.flush()
    await output_mgr.stop_all()

    if result.snapshot:
        if console:
            console.render_summary(result.snapshot, result.threshold_results)
        for output in output_mgr.outputs:
            if isinstance(output, _SummaryOutput):
                output.write_summary(result.snapshot, result.threshold_results)

    return result


async def _progress_loop(controller: RunController) -> None:
    """Periodically write a single-line progress update."""
    from rampa.cli._progress import write_progress
    from rampa.events import SnapshotEvent

    async for event in controller.events():
        if isinstance(event, SnapshotEvent):
            write_progress(event.snapshot)


async def _drain_events(
    controller: RunController,
    path: str,
) -> None:
    """Drain engine events to a JSONL file.

    Parameters
    ----------
    controller : RunController
        The run controller to subscribe to.
    path : str
        Output file path.
    """
    out = pathlib.Path(path)
    with out.open("w") as f:
        async for event in controller.events():
            line = json.dumps(serialize_event(event))
            f.write(line + "\n")


def status_to_exit_code(status: RunStatus) -> ExitCode:
    """Map a RunStatus to a process exit code.

    Parameters
    ----------
    status : RunStatus
        The headless run status.

    Returns
    -------
    ExitCode
        The corresponding process exit code.

    >>> status_to_exit_code(RunStatus.PASSED)
    <ExitCode.OK: 0>
    >>> status_to_exit_code(RunStatus.THRESHOLD_FAILED)
    <ExitCode.THRESHOLD_FAILURE: 1>
    """
    return _STATUS_TO_EXIT.get(status, ExitCode.ITERATION_EXCEPTION)
