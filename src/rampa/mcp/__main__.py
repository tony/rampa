"""Allow running the MCP server with ``python -m rampa.mcp``.

>>> import rampa.mcp.__main__
"""

from __future__ import annotations

from rampa.mcp.server import main

if __name__ == "__main__":
    main()
