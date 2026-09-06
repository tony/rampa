"""FastMCP server for rampa.

Creates the MCP server instance, registers tools and resources, and
provides the ``main()`` entry point.

>>> import rampa.mcp.server
"""

from __future__ import annotations

import logging

import fastmcp
from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware

logger = logging.getLogger(__name__)

_SSE_DEPRECATED = (
    "the sse transport was deprecated in MCP revision 2025-03-26 and is "
    "scheduled for removal; set FASTMCP_TRANSPORT to http (Streamable HTTP) or stdio"
)


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

    from rampa.mcp.resources import register as register_resources, register_completions

    register_resources(mcp)
    register_completions(mcp)


def _reject_deprecated_transport(transport: str) -> None:
    """Raise if the MCP specification has deprecated this transport.

    HTTP+SSE was deprecated in revision 2025-03-26 and superseded by
    Streamable HTTP. ``stdio``, ``http``, and ``streamable-http`` are
    unaffected; fastmcp routes the latter two to the same Streamable HTTP
    implementation.

    Parameters
    ----------
    transport : str
        Transport name, normally from ``fastmcp.settings.transport``.

    Raises
    ------
    ValueError
        If ``transport`` names a deprecated transport.

    >>> _reject_deprecated_transport("stdio")
    >>> _reject_deprecated_transport("http")
    >>> _reject_deprecated_transport("sse")
    Traceback (most recent call last):
    ValueError: the sse transport was deprecated in MCP revision 2025-03-26 ...
    """
    if transport == "sse":
        raise ValueError(_SSE_DEPRECATED)


def main() -> None:
    """Entry point for the rampa MCP server."""
    transport = fastmcp.settings.transport
    _reject_deprecated_transport(transport)
    mcp = build_mcp_server()
    mcp.run(transport)
