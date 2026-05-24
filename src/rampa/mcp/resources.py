"""MCP resource URI templates for rampa.

>>> import rampa.mcp.resources
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register all MCP resources."""
