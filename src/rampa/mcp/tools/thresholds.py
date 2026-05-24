"""Threshold query MCP tools.

>>> import rampa.mcp.tools.thresholds
"""

from __future__ import annotations

import typing as t

from rampa.mcp.tools.runs import get_registry

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


async def get_thresholds_impl(run_id: str) -> dict[str, t.Any]:
    """Get threshold evaluation results for a run.

    Parameters
    ----------
    run_id : str
        The run identifier.

    Returns
    -------
    dict[str, Any]
        Threshold results.
    """
    registry = get_registry()
    record = registry.get(run_id)
    if record is None:
        return {"error": f"run {run_id!r} not found"}

    if record.result is None:
        return {"run_id": run_id, "thresholds": [], "status": "running"}

    return {
        "run_id": run_id,
        "status": record.result.status.value,
        "thresholds": [
            {
                "source": r.source,
                "passed": r.passed,
                "lhs": r.lhs,
                "rhs": r.rhs,
            }
            for r in record.result.threshold_results
        ],
    }


def register(mcp: FastMCP) -> None:
    """Register threshold query tools."""
    mcp.tool(
        name="get_thresholds",
        description="Get threshold evaluation results for a test run.",
    )(get_thresholds_impl)
