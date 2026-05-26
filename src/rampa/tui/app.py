"""Textual-based TUI dashboard for live load test monitoring.

Uses ``call_from_thread()`` for high-frequency metric updates to avoid
competing with keystroke events on the message bus.

>>> import rampa.tui.app
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from rampa.loader import TestPlan


def run_tui(plan: TestPlan) -> int:
    """Launch the TUI dashboard for a test plan.

    Parameters
    ----------
    plan : TestPlan
        Resolved test plan from the loader.

    Returns
    -------
    int
        Process exit code.

    >>> import rampa.tui.app
    """
    import importlib.util

    if importlib.util.find_spec("textual") is None:
        msg = "textual is required for --tui. Install with: pip install rampa[tui]"
        raise RuntimeError(msg)

    from rampa.tui._dashboard import build_app

    app_cls = build_app()
    app = app_cls(plan=plan)
    app.run()
    return app.exit_code
