"""Process-local registry for tracking active and completed test runs.

The registry holds ``RunController`` references for active runs and
``RunResult`` objects for completed runs. Controllers are released
after completion to free resources (metric engine threads, sessions).

>>> import rampa.mcp.registry
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from rampa.engine import RunController
from rampa.events import EngineEvent, RunResult

logger = logging.getLogger(__name__)


@dataclass
class RuntimeRun:
    """Non-serializable async state for an active run.

    >>> import rampa.mcp.registry
    """

    controller: RunController
    wait_task: asyncio.Task[RunResult]
    event_task: asyncio.Task[None]


@dataclass
class RunRecord:
    """Per-run state in the registry.

    >>> r = RunRecord(run_id="abc", script_path="test.py", started_at=0.0)
    >>> r.is_complete
    False
    """

    run_id: str
    script_path: str
    started_at: float
    runtime: RuntimeRun | None = None
    result: RunResult | None = None
    events: list[EngineEvent] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Return True if the run has finished.

        >>> r = RunRecord(run_id="x", script_path="t.py", started_at=0.0)
        >>> r.is_complete
        False
        """
        return self.result is not None


class RunRegistry:
    """Process-local registry of active and completed runs.

    >>> reg = RunRegistry()
    >>> reg.list_all()
    []
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def register(self, record: RunRecord) -> None:
        """Add a new run to the registry.

        Parameters
        ----------
        record : RunRecord
            The run record to register.

        >>> reg = RunRegistry()
        >>> rec = RunRecord(run_id="r1", script_path="t.py", started_at=0.0)
        >>> reg.register(rec)
        >>> reg.get("r1") is rec
        True
        """
        self._runs[record.run_id] = record

    def get(self, run_id: str) -> RunRecord | None:
        """Look up a run by ID.

        Parameters
        ----------
        run_id : str
            The run identifier.

        Returns
        -------
        RunRecord | None
            The run record, or None if not found.
        """
        return self._runs.get(run_id)

    def list_all(self) -> list[RunRecord]:
        """Return all registered runs.

        Returns
        -------
        list[RunRecord]
            All run records.
        """
        return list(self._runs.values())

    def complete(self, run_id: str, result: RunResult) -> None:
        """Mark a run as completed and release its runtime resources.

        Parameters
        ----------
        run_id : str
            The run identifier.
        result : RunResult
            The final run result.

        >>> reg = RunRegistry()
        >>> rec = RunRecord(run_id="r1", script_path="t.py", started_at=0.0)
        >>> reg.register(rec)
        >>> from rampa.events import RunResult, RunStatus
        >>> result = RunResult(
        ...     run_id="r1",
        ...     status=RunStatus.PASSED,
        ...     snapshot=None,
        ...     threshold_results=[],
        ... )
        >>> reg.complete("r1", result)
        >>> rec.is_complete
        True
        >>> rec.runtime is None
        True
        """
        record = self._runs.get(run_id)
        if record is not None:
            record.result = result
            record.runtime = None
            logger.info("run %s completed: %s", run_id, result.status)
