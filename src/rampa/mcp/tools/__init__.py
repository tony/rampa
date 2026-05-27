"""MCP tool registration for rampa.

>>> import rampa.mcp.tools
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register all MCP tools.

    Parameters
    ----------
    mcp : FastMCP
        The MCP server instance.
    """
    from rampa.mcp.tools.runs import register as register_runs

    register_runs(mcp)

    from rampa.mcp.tools.metrics import register as register_metrics

    register_metrics(mcp)

    from rampa.mcp.tools.thresholds import register as register_thresholds

    register_thresholds(mcp)

    from rampa.mcp.tools.discovery import register as register_discovery

    register_discovery(mcp)
