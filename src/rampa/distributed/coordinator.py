"""Coordinator server for distributed rampa execution.

Accepts WebSocket connections from remote workers, distributes work
segments, aggregates samples, and evaluates thresholds centrally.

>>> import rampa.distributed.coordinator
"""

from __future__ import annotations

import logging
import queue
import typing as t

from rampa._types import Sample, make_sample
from rampa.distributed.protocol import (
    Envelope,
    MessageType,
)
from rampa.distributed.segment import ExecutionSegment

logger = logging.getLogger(__name__)


@t.runtime_checkable
class WorkerConnection(t.Protocol):
    """Protocol for a connected remote worker."""

    worker_id: str
    segment: ExecutionSegment

    async def send(self, envelope: Envelope) -> None:
        """Send a message to the worker."""
        ...

    async def close(self) -> None:
        """Close the connection."""
        ...


class CoordinatorState:
    """Tracks connected workers and aggregated state.

    >>> cs = CoordinatorState()
    >>> cs.worker_count
    0
    """

    def __init__(self) -> None:
        self._workers: dict[str, WorkerConnection] = {}
        self._seq: int = 0

    @property
    def worker_count(self) -> int:
        """Return the number of connected workers."""
        return len(self._workers)

    def register_worker(self, conn: WorkerConnection) -> None:
        """Register a connected worker.

        Parameters
        ----------
        conn : WorkerConnection
            The worker connection.
        """
        self._workers[conn.worker_id] = conn
        logger.info("worker registered: %s", conn.worker_id)

    def remove_worker(self, worker_id: str) -> None:
        """Remove a disconnected worker.

        Parameters
        ----------
        worker_id : str
            The worker to remove.
        """
        self._workers.pop(worker_id, None)
        logger.info("worker removed: %s", worker_id)

    async def broadcast(self, msg_type: MessageType, payload: dict[str, t.Any]) -> None:
        """Send a message to all connected workers.

        Parameters
        ----------
        msg_type : MessageType
            Message type.
        payload : dict[str, Any]
            Message payload.
        """
        self._seq += 1
        envelope = Envelope(
            msg_type=msg_type,
            worker_id="coordinator",
            seq=self._seq,
            payload=payload,
        )
        for conn in list(self._workers.values()):
            try:
                await conn.send(envelope)
            except Exception:
                logger.warning("failed to send to %s", conn.worker_id)


def ingest_remote_samples(
    payload: dict[str, t.Any],
    sample_queue: queue.SimpleQueue[Sample | None],
) -> int:
    """Ingest samples from a remote worker into the local MetricEngine.

    Parameters
    ----------
    payload : dict[str, Any]
        The ``samples`` message payload from a worker.
    sample_queue : queue.SimpleQueue[Sample | None]
        The engine's sample queue.

    Returns
    -------
    int
        Number of samples ingested.

    >>> import queue as q
    >>> sq: q.SimpleQueue[Sample | None] = q.SimpleQueue()
    >>> payload = {"samples": [
    ...     {"m": "reqs", "v": 1.0, "t": 1000, "g": {}},
    ...     {"m": "dur", "v": 45.2, "t": 2000, "g": {"status": "200"}},
    ... ]}
    >>> ingest_remote_samples(payload, sq)
    2
    >>> sq.get_nowait().metric
    'reqs'
    """
    raw_samples = payload.get("samples", [])
    count = 0
    for raw in raw_samples:
        sample = make_sample(
            raw["m"],
            raw["v"],
            raw.get("g", {}),
        )
        sample_queue.put(sample)
        count += 1
    return count
