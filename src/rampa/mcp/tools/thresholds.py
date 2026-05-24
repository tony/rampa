"""Threshold query MCP tools.

>>> import rampa.mcp.tools.thresholds
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register threshold query tools."""
