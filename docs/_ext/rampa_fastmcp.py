"""Docs-only FastMCP registration shim for rampa tools.

The runtime server registers its tools inside ``build_mcp_server()`` so the
live FastMCP instance stays self-contained. The Sphinx FastMCP tool collector
documents module-level ``register(server)`` hooks, so this module mirrors the
public tool signatures without changing runtime behavior.
"""

from __future__ import annotations

import types
import typing as t

from pydantic import Field

READONLY_TAGS = {"readonly", "rampa"}
MUTATING_TAGS = {"mutating", "rampa"}
DOCS_ONLY_MESSAGE = "Documentation signature only."


async def start_run(
    script_path: t.Annotated[
        str,
        Field(description="Path to the test script."),
    ],
    vus: t.Annotated[
        int | None,
        Field(default=None, description="Override VU count."),
    ] = None,
    duration: t.Annotated[
        str | None,
        Field(default=None, description="Override duration (e.g. 30s, 1m)."),
    ] = None,
    scenario: t.Annotated[
        str | None,
        Field(default=None, description="Run a specific scenario only."),
    ] = None,
) -> dict[str, str]:
    """Start a load test from a Python script."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, start_run).__fastmcp__ = types.SimpleNamespace(
    name="start_run",
    title="Start Run",
    tags=MUTATING_TAGS | {"lifecycle"},
    annotations=None,
)


async def stop_run(
    run_id: t.Annotated[
        str,
        Field(description="The run identifier."),
    ],
    reason: t.Annotated[
        str | None,
        Field(default=None, description="Optional stop reason."),
    ] = None,
) -> dict[str, str]:
    """Stop a running load test. Idempotent."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, stop_run).__fastmcp__ = types.SimpleNamespace(
    name="stop_run",
    title="Stop Run",
    tags=MUTATING_TAGS | {"lifecycle"},
    annotations=None,
)


async def get_status(
    run_id: t.Annotated[
        str,
        Field(description="The run identifier."),
    ],
) -> dict[str, t.Any]:
    """Get current status of a test run."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, get_status).__fastmcp__ = types.SimpleNamespace(
    name="get_status",
    title="Get Status",
    tags=READONLY_TAGS | {"lifecycle"},
    annotations=None,
)


async def list_runs() -> list[dict[str, str]]:
    """List all active and completed test runs."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, list_runs).__fastmcp__ = types.SimpleNamespace(
    name="list_runs",
    title="List Runs",
    tags=READONLY_TAGS | {"lifecycle"},
    annotations=None,
)


async def get_metrics(
    run_id: t.Annotated[
        str,
        Field(description="The run identifier."),
    ],
    metric_name: t.Annotated[
        str | None,
        Field(default=None, description="Filter to a specific metric."),
    ] = None,
) -> dict[str, t.Any]:
    """Get metrics for a test run. Optionally filter by metric name."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, get_metrics).__fastmcp__ = types.SimpleNamespace(
    name="get_metrics",
    title="Get Metrics",
    tags=READONLY_TAGS | {"metrics"},
    annotations=None,
)


async def get_thresholds(
    run_id: t.Annotated[
        str,
        Field(description="The run identifier."),
    ],
) -> dict[str, t.Any]:
    """Get threshold evaluation results for a test run."""
    raise NotImplementedError(DOCS_ONLY_MESSAGE)


t.cast(t.Any, get_thresholds).__fastmcp__ = types.SimpleNamespace(
    name="get_thresholds",
    title="Get Thresholds",
    tags=READONLY_TAGS | {"thresholds"},
    annotations=None,
)
