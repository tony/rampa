"""MCP resource URI templates for rampa.

Resources expose read-only run state via URI templates following
RFC 6570 patterns.

>>> import rampa.mcp.resources
"""

from __future__ import annotations

import json
import typing as t

from rampa.events import serialize_event
from rampa.mcp.tools.runs import get_registry

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register all MCP resources."""

    @mcp.resource("rampa://runs", title="All Runs", mime_type="application/json")
    async def all_runs() -> str:
        """List all runs as JSON."""
        registry = get_registry()
        runs = [
            {
                "run_id": r.run_id,
                "script_path": r.script_path,
                "status": r.result.status.value if r.result else "running",
            }
            for r in registry.list_all()
        ]
        return json.dumps(runs, indent=2)

    @mcp.resource(
        "rampa://runs/{run_id}",
        title="Run Details",
        mime_type="application/json",
    )
    async def run_details(run_id: str) -> str:
        """Get details for a specific run."""
        registry = get_registry()
        record = registry.get(run_id)
        if record is None:
            return json.dumps({"error": f"run {run_id!r} not found"})
        data: dict[str, t.Any] = {
            "run_id": record.run_id,
            "script_path": record.script_path,
            "completed": record.is_complete,
            "event_count": len(record.events),
        }
        if record.result:
            data["status"] = record.result.status.value
        return json.dumps(data, indent=2)

    @mcp.resource(
        "rampa://runs/{run_id}/metrics",
        title="Run Metrics",
        mime_type="application/json",
    )
    async def run_metrics(run_id: str) -> str:
        """Get all metrics for a run."""
        registry = get_registry()
        record = registry.get(run_id)
        if record is None:
            return json.dumps({"error": f"run {run_id!r} not found"})
        snapshot = None
        if record.result and record.result.snapshot:
            snapshot = record.result.snapshot
        elif record.runtime:
            snapshot = record.runtime.controller.snapshot()
        if snapshot is None:
            return json.dumps({"run_id": run_id, "metrics": {}})
        return json.dumps(
            {"run_id": run_id, "duration": snapshot.duration, "metrics": snapshot.values},
            indent=2,
        )

    @mcp.resource(
        "rampa://runs/{run_id}/metrics/{name}",
        title="Specific Metric",
        mime_type="application/json",
    )
    async def run_metric(run_id: str, name: str) -> str:
        """Get a specific metric for a run."""
        registry = get_registry()
        record = registry.get(run_id)
        if record is None:
            return json.dumps({"error": f"run {run_id!r} not found"})
        snapshot = None
        if record.result and record.result.snapshot:
            snapshot = record.result.snapshot
        elif record.runtime:
            snapshot = record.runtime.controller.snapshot()
        if snapshot is None or name not in snapshot.values:
            return json.dumps({"error": f"metric {name!r} not found"})
        return json.dumps(
            {"run_id": run_id, "metric": name, "values": snapshot.values[name]},
            indent=2,
        )

    @mcp.resource(
        "rampa://runs/{run_id}/thresholds",
        title="Threshold Results",
        mime_type="application/json",
    )
    async def run_thresholds(run_id: str) -> str:
        """Get threshold results for a run."""
        registry = get_registry()
        record = registry.get(run_id)
        if record is None:
            return json.dumps({"error": f"run {run_id!r} not found"})
        if record.result is None:
            return json.dumps({"run_id": run_id, "thresholds": []})
        return json.dumps(
            {
                "run_id": run_id,
                "thresholds": [
                    {"source": r.source, "passed": r.passed, "lhs": r.lhs, "rhs": r.rhs}
                    for r in record.result.threshold_results
                ],
            },
            indent=2,
        )

    @mcp.resource(
        "rampa://runs/{run_id}/events",
        title="Event Log",
        mime_type="application/json",
    )
    async def run_events(run_id: str) -> str:
        """Get accumulated events for a run."""
        registry = get_registry()
        record = registry.get(run_id)
        if record is None:
            return json.dumps({"error": f"run {run_id!r} not found"})
        events = [serialize_event(event) for event in record.events]
        return json.dumps({"run_id": run_id, "events": events}, indent=2)
