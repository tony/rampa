"""Test runner — compatibility wrapper over the headless engine.

This module preserves the ``run_test()`` API for the CLI while delegating
to ``Engine``/``RunController`` internally.

>>> import rampa.runner
"""

from __future__ import annotations

import logging

from rampa.engine import Engine, EngineOptions
from rampa.errors import ExitCode
from rampa.events import RunResult, RunStatus
from rampa.loader import TestPlan
from rampa.output import ConsoleOutput, JSONOutput, OutputManager

logger = logging.getLogger(__name__)

_STATUS_TO_EXIT: dict[RunStatus, ExitCode] = {
    RunStatus.PASSED: ExitCode.OK,
    RunStatus.THRESHOLD_FAILED: ExitCode.THRESHOLD_FAILURE,
    RunStatus.SETUP_FAILED: ExitCode.SETUP_FAILURE,
    RunStatus.EXECUTION_FAILED: ExitCode.ITERATION_EXCEPTION,
    RunStatus.TEARDOWN_FAILED: ExitCode.ITERATION_EXCEPTION,
    RunStatus.STOPPED: ExitCode.ABORTED,
}


async def run_test(
    plan: TestPlan,
    json_output_path: str | None = None,
    quiet: bool = False,
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

    output_mgr = OutputManager()
    console = ConsoleOutput() if not quiet else None
    if console:
        output_mgr.add(console)

    json_out: JSONOutput | None = None
    if json_output_path:
        json_out = JSONOutput(json_output_path)
        output_mgr.add(json_out)

    await output_mgr.start_all()

    result = await controller.wait()

    output_mgr.buffer_samples(output_samples)
    await output_mgr.flush()
    await output_mgr.stop_all()

    if result.snapshot:
        if console:
            console.render_summary(result.snapshot, result.threshold_results)
        if json_out:
            json_out.write_summary(result.snapshot, result.threshold_results)

    return result


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
