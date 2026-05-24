"""Metric query MCP tools.

>>> import rampa.mcp.tools.metrics
"""

from __future__ import annotations

import typing as t

from rampa.mcp.tools.runs import get_registry

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


async def get_metrics_impl(
    run_id: str,
    metric_name: str | None = None,
) -> dict[str, t.Any]:
    """Get metrics for a run, optionally filtered by name.

    Parameters
    ----------
    run_id : str
        The run identifier.
    metric_name : str | None
        Filter to a specific metric.

    Returns
    -------
    dict[str, Any]
        Metric data.
    """
    registry = get_registry()
    record = registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}

    snapshot = None
    if record.result and record.result.snapshot:
        snapshot = record.result.snapshot
    elif record.runtime:
        snapshot = record.runtime.controller.snapshot()

    if snapshot is None:
        return {"run_id": run_id, "metrics": {}}

    if metric_name:
        value = snapshot.values.get(metric_name)
        if value is None:
            return {"error": f"metric {metric_name!r} not found"}
        return {"run_id": run_id, "metric": metric_name, "values": value}

    return {
        "run_id": run_id,
        "duration": snapshot.duration,
        "metrics": snapshot.values,
    }


def register(mcp: FastMCP) -> None:
    """Register metric query tools."""
    mcp.tool(
        name="get_metrics",
        description="Get metrics for a test run. Optionally filter by metric name.",
    )(get_metrics_impl)
