"""Scenario discovery and config inspection MCP tools.

>>> import rampa.mcp.tools.discovery
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


async def discover_scenarios_impl(script_path: str) -> dict[str, t.Any]:
    """Load a script and return its scenarios without running.

    Parameters
    ----------
    script_path : str
        Path to the test script.

    Returns
    -------
    dict[str, Any]
        Scenario names, executor types, configs, and lifecycle hooks.
    """
    from rampa.loader import load_test

    plan = load_test(script_path)

    scenarios: dict[str, dict[str, t.Any]] = {}
    for name, (cfg, _fn) in plan.scenarios.items():
        scenarios[name] = {
            "executor": cfg.executor,
            "vus": cfg.vus,
            "duration": str(cfg.duration) if cfg.duration else None,
            "iterations": cfg.iterations,
            "rate": cfg.rate,
        }

    return {
        "script": script_path,
        "scenarios": scenarios,
        "thresholds": dict(plan.config.thresholds),
        "has_setup": plan.setup_fn is not None,
        "has_teardown": plan.teardown_fn is not None,
    }


async def inspect_config_impl(script_path: str) -> dict[str, t.Any]:
    """Return the fully resolved configuration for a script.

    Parameters
    ----------
    script_path : str
        Path to the test script.

    Returns
    -------
    dict[str, Any]
        Resolved config including all defaults.
    """
    return await discover_scenarios_impl(script_path)


def register(mcp: FastMCP) -> None:
    """Register discovery tools on the MCP server."""
    mcp.tool(
        name="discover_scenarios",
        description="Load a script and list its scenarios without running.",
    )(discover_scenarios_impl)

    mcp.tool(
        name="inspect_config",
        description="Show the fully resolved test configuration.",
    )(inspect_config_impl)
