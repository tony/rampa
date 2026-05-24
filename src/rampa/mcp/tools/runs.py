"""Run lifecycle MCP tools.

>>> import rampa.mcp.tools.runs
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register run lifecycle tools."""
