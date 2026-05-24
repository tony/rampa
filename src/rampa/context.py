"""Context variables for rampa logging and tracing.

These variables propagate run, scenario, and worker context through the
async call stack without explicit parameter threading.

>>> import rampa.context
"""

from __future__ import annotations

import contextvars

run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "rampa_run_id",
    default=None,
)
"""Current run identifier.

>>> run_id_var.get() is None
True
"""

scenario_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "rampa_scenario",
    default=None,
)
"""Current scenario name.

>>> scenario_var.get() is None
True
"""

worker_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "rampa_worker_id",
    default=None,
)
"""Current worker identifier.

>>> worker_id_var.get() is None
True
"""

iteration_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "rampa_iteration",
    default=None,
)
"""Current iteration number.

>>> iteration_var.get() is None
True
"""
