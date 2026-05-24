"""FastMCP server for rampa.

Creates the MCP server instance, registers tools and resources, and
provides the ``main()`` entry point.

>>> import rampa.mcp.server
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

logger = logging.getLogger(__name__)


def build_mcp_server() -> FastMCP:
    """Build and configure the rampa MCP server.

    Returns
    -------
    FastMCP
        Configured MCP server with tools and resources registered.

    >>> server = build_mcp_server()
    >>> server.name
    'rampa'
    """
    mcp = FastMCP(
        name="rampa",
        instructions=(
            "Load testing framework. Start test runs, query metrics, evaluate thresholds."
        ),
        middleware=[
            TimingMiddleware(),
            ErrorHandlingMiddleware(),
        ],
    )

    _register_all(mcp)
    return mcp


def _register_all(mcp: FastMCP) -> None:
    """Register all tools and resources on the MCP server."""
    from rampa.mcp.tools import register as register_tools

    register_tools(mcp)

    from rampa.mcp.resources import register as register_resources

    register_resources(mcp)


def main() -> None:
    """Entry point for the rampa MCP server."""
    mcp = build_mcp_server()
    mcp.run()
