"""Run lifecycle MCP tools.

Tools for starting, stopping, querying, and listing load test runs.

>>> import rampa.mcp.tools.runs
"""

from __future__ import annotations

import asyncio
import logging
import time
import typing as t

from rampa.engine import Engine
from rampa.loader import load_test
from rampa.mcp.registry import RunRecord, RunRegistry, RuntimeRun

if t.TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)

_registry = RunRegistry()
_background_tasks: set[asyncio.Task[None]] = set()


def get_registry() -> RunRegistry:
    """Return the global run registry.

    >>> reg = get_registry()
    >>> isinstance(reg, RunRegistry)
    True
    """
    return _registry


async def _drain_events(record: RunRecord) -> None:
    """Background task that drains events from a running controller."""
    if record.runtime is None:
        return
    try:
        async for event in record.runtime.controller.events():
            record.events.append(event)
    except Exception:
        logger.exception("event drain error for run %s", record.run_id)


async def _wait_and_complete(record: RunRecord) -> None:
    """Background task that waits for run completion and updates registry."""
    if record.runtime is None:
        return
    try:
        result = await record.runtime.wait_task
        _registry.complete(record.run_id, result)
    except Exception:
        logger.exception("wait error for run %s", record.run_id)


async def start_run_impl(
    script_path: str,
    vus: int | None = None,
    duration: str | None = None,
    scenario: str | None = None,
) -> dict[str, str]:
    """Start a load test run.

    Parameters
    ----------
    script_path : str
        Path to the test script.
    vus : int | None
        Override VU count.
    duration : str | None
        Override duration (e.g. "30s").
    scenario : str | None
        Run a specific scenario only.

    Returns
    -------
    dict[str, str]
        Run ID and status.
    """
    try:
        plan = load_test(script_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}

    if vus is not None:
        for cfg, _fn in plan.scenarios.values():
            cfg.vus = vus

    if duration is not None:
        from rampa.config import parse_duration

        td = parse_duration(duration)
        for cfg, _fn in plan.scenarios.values():
            cfg.duration = td

    if scenario is not None:
        if scenario not in plan.scenarios:
            return {"error": f"scenario {scenario!r} not found"}
        plan.scenarios = {scenario: plan.scenarios[scenario]}

    controller = await Engine(plan).start()
    run_id = controller.run_id

    wait_task = asyncio.create_task(controller.wait())

    record = RunRecord(
        run_id=run_id,
        script_path=script_path,
        started_at=time.monotonic(),
    )

    event_task = asyncio.create_task(_drain_events(record))

    record.runtime = RuntimeRun(
        controller=controller,
        wait_task=wait_task,
        event_task=event_task,
    )

    _registry.register(record)

    completion_task = asyncio.create_task(_wait_and_complete(record))
    _background_tasks.add(completion_task)
    completion_task.add_done_callback(_background_tasks.discard)

    logger.info("started run %s from %s", run_id, script_path)
    return {"run_id": run_id, "status": "started"}


async def stop_run_impl(
    run_id: str,
    reason: str | None = None,
) -> dict[str, str]:
    """Stop a running test. Idempotent.

    Parameters
    ----------
    run_id : str
        The run identifier.
    reason : str | None
        Optional stop reason.

    Returns
    -------
    dict[str, str]
        Status update.
    """
    record = _registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}
    if record.runtime is None:
        return {"run_id": run_id, "status": "already_completed"}
    await record.runtime.controller.stop(reason)
    return {"run_id": run_id, "status": "stopping"}


async def get_status_impl(run_id: str) -> dict[str, t.Any]:
    """Get current status of a run.

    Parameters
    ----------
    run_id : str
        The run identifier.

    Returns
    -------
    dict[str, Any]
        Run status information.
    """
    record = _registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}
    if record.result is not None:
        return {
            "run_id": run_id,
            "status": record.result.status.value,
            "completed": True,
        }
    if record.runtime is not None:
        snap = record.runtime.controller.snapshot()
        return {
            "run_id": run_id,
            "status": "running",
            "completed": False,
            "has_snapshot": snap is not None,
        }
    return {"run_id": run_id, "status": "unknown"}


async def list_runs_impl() -> list[dict[str, str]]:
    """List all active and completed runs.

    Returns
    -------
    list[dict[str, str]]
        Summary of each run.
    """
    return [
        {
            "run_id": r.run_id,
            "script_path": r.script_path,
            "status": r.result.status.value if r.result else "running",
        }
        for r in _registry.list_all()
    ]


async def pause_run_impl(run_id: str) -> dict[str, str]:
    """Pause a running test. Idempotent.

    Parameters
    ----------
    run_id : str
        The run identifier.

    Returns
    -------
    dict[str, str]
        Status update.
    """
    record = _registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}
    if record.runtime is None:
        return {"run_id": run_id, "status": "already_completed"}
    record.runtime.controller.pause()
    return {"run_id": run_id, "status": "paused"}


async def resume_run_impl(run_id: str) -> dict[str, str]:
    """Resume a paused test. Idempotent.

    Parameters
    ----------
    run_id : str
        The run identifier.

    Returns
    -------
    dict[str, str]
        Status update.
    """
    record = _registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}
    if record.runtime is None:
        return {"run_id": run_id, "status": "already_completed"}
    record.runtime.controller.resume()
    return {"run_id": run_id, "status": "resumed"}


def register(mcp: FastMCP) -> None:
    """Register run lifecycle tools on the MCP server."""
    mcp.tool(
        name="start_run",
        description="Start a load test from a Python script.",
    )(start_run_impl)

    mcp.tool(
        name="stop_run",
        description="Stop a running load test. Idempotent.",
    )(stop_run_impl)

    mcp.tool(
        name="pause_run",
        description="Pause a running load test. Executors block before next iteration.",
    )(pause_run_impl)

    mcp.tool(
        name="resume_run",
        description="Resume a paused load test.",
    )(resume_run_impl)

    mcp.tool(
        name="get_status",
        description="Get current status of a test run.",
    )(get_status_impl)

    mcp.tool(
        name="list_runs",
        description="List all active and completed test runs.",
    )(list_runs_impl)
