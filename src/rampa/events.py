"""Typed engine events and run status for rampa.

Events are observational — engine correctness does not depend on an event
consumer being active. Frontends subscribe to events for live updates.

>>> import rampa.events
"""

from __future__ import annotations

import dataclasses
import enum
import typing as t
import uuid
from dataclasses import dataclass, field

from rampa.metrics import MetricSnapshot
from rampa.thresholds import ThresholdResult


class RunStatus(enum.StrEnum):
    """Final status of a completed test run.

    >>> RunStatus.PASSED.value
    'passed'
    >>> RunStatus.THRESHOLD_FAILED.value
    'threshold_failed'
    """

    PASSED = "passed"
    THRESHOLD_FAILED = "threshold_failed"
    SETUP_FAILED = "setup_failed"
    EXECUTION_FAILED = "execution_failed"
    TEARDOWN_FAILED = "teardown_failed"
    STOPPED = "stopped"


def _make_run_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass(frozen=True)
class EngineEvent:
    """Base class for all engine events.

    >>> e = EngineEvent(run_id="abc", timestamp_ns=0)
    >>> e.run_id
    'abc'
    """

    run_id: str
    timestamp_ns: int


@dataclass(frozen=True)
class PhaseEvent(EngineEvent):
    """Lifecycle phase transition.

    >>> e = PhaseEvent(run_id="abc", timestamp_ns=0, phase="setup")
    >>> e.phase
    'setup'
    """

    phase: t.Literal["setup", "execute", "teardown", "complete"]


@dataclass(frozen=True)
class PauseEvent(EngineEvent):
    """Emitted when execution is paused.

    >>> e = PauseEvent(run_id="x", timestamp_ns=0)
    >>> e.run_id
    'x'
    """


@dataclass(frozen=True)
class ResumeEvent(EngineEvent):
    """Emitted when execution resumes after a pause.

    >>> e = ResumeEvent(run_id="x", timestamp_ns=0, paused_seconds=1.5)
    >>> e.paused_seconds
    1.5
    """

    paused_seconds: float


@dataclass(frozen=True)
class SnapshotEvent(EngineEvent):
    """Periodic metric snapshot.

    >>> from rampa.metrics import MetricSnapshot
    >>> snap = MetricSnapshot(timestamp=0, duration=1.0, values={})
    >>> e = SnapshotEvent(run_id="x", timestamp_ns=0, snapshot=snap)
    >>> e.snapshot.duration
    1.0
    """

    snapshot: MetricSnapshot


@dataclass(frozen=True)
class ThresholdEvent(EngineEvent):
    """Threshold evaluation results.

    >>> e = ThresholdEvent(run_id="x", timestamp_ns=0, results=[])
    >>> len(e.results)
    0
    """

    results: list[ThresholdResult]


@dataclass(frozen=True)
class RunResult:
    """Result of a completed test run.

    >>> r = RunResult(
    ...     run_id="abc",
    ...     status=RunStatus.PASSED,
    ...     snapshot=None,
    ...     threshold_results=[],
    ... )
    >>> r.status
    <RunStatus.PASSED: 'passed'>
    """

    run_id: str
    status: RunStatus
    snapshot: MetricSnapshot | None
    threshold_results: list[ThresholdResult]
    error: BaseException | None = field(default=None, repr=False)
    stop_reason: str | None = None


def serialize_event(event: EngineEvent) -> dict[str, t.Any]:
    """Serialize an engine event to a JSON-compatible dict.

    Adds a ``type`` key with the event class name. All dataclass
    fields are included via ``dataclasses.asdict()``.

    Parameters
    ----------
    event : EngineEvent
        The event to serialize.

    Returns
    -------
    dict[str, Any]
        JSON-serializable dictionary.

    >>> e = PhaseEvent(run_id="abc", timestamp_ns=0, phase="setup")
    >>> d = serialize_event(e)
    >>> d["type"]
    'PhaseEvent'
    >>> d["phase"]
    'setup'
    """
    d = dataclasses.asdict(event)
    d["type"] = type(event).__name__
    return d
