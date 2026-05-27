"""Remote worker client for distributed rampa execution.

Connects to a coordinator via WebSocket, receives work assignments,
runs load tests locally, and streams samples back.

>>> import rampa.distributed.worker_client
"""

from __future__ import annotations

import asyncio
import functools
import logging
import queue
import typing as t

from rampa._types import Sample
from rampa.distributed.protocol import (
    Envelope,
    MessageType,
    encode,
)

logger = logging.getLogger(__name__)


def _samples_to_wire(samples: list[Sample]) -> list[dict[str, t.Any]]:
    """Convert samples to compact wire format.

    Parameters
    ----------
    samples : list[Sample]
        Samples to convert.

    Returns
    -------
    list[dict[str, Any]]
        Compact dicts with short keys for MessagePack efficiency.

    >>> from rampa._types import Sample
    >>> s = Sample(metric="reqs", value=1.0, timestamp=1000, tags={"a": "b"})
    >>> wire = _samples_to_wire([s])
    >>> wire[0]["m"]
    'reqs'
    >>> wire[0]["g"]
    {'a': 'b'}
    """
    return [{"m": s.metric, "v": s.value, "t": s.timestamp, "g": s.tags} for s in samples]


class WorkerClient:
    """Remote worker that connects to a coordinator.

    Parameters
    ----------
    coordinator_url : str
        WebSocket URL of the coordinator.
    worker_id : str
        Unique identifier for this worker.
    batch_size : int
        Sample batch size for streaming.

    >>> wc = WorkerClient("ws://localhost:6565", "w-0")
    >>> wc._worker_id
    'w-0'
    """

    def __init__(
        self,
        coordinator_url: str,
        worker_id: str,
        batch_size: int = 1000,
    ) -> None:
        self._url = coordinator_url
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._seq = 0
        self._ws: t.Any = None
        self._session: t.Any = None

    async def connect(self) -> None:
        """Connect to the coordinator and send registration."""
        import aiohttp

        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self._url)
        await self._send(
            MessageType.REGISTER,
            {"version": "0.0.1", "worker_id": self._worker_id},
        )
        logger.info("connected to coordinator: %s", self._url)

    async def _send(self, msg_type: MessageType, payload: dict[str, t.Any]) -> None:
        self._seq += 1
        envelope = Envelope(
            msg_type=msg_type,
            worker_id=self._worker_id,
            seq=self._seq,
            payload=payload,
        )
        await self._ws.send_bytes(encode(envelope))

    async def stream_samples(
        self,
        sample_queue: queue.SimpleQueue[Sample | None],
    ) -> None:
        """Drain samples from local queue and stream to coordinator.

        Parameters
        ----------
        sample_queue : queue.SimpleQueue[Sample | None]
            Local engine sample queue.
        """
        loop = asyncio.get_running_loop()
        buffer: list[Sample] = []
        while True:
            try:
                sample = await loop.run_in_executor(
                    None, functools.partial(sample_queue.get, timeout=0.1)
                )
            except Exception:
                if buffer:
                    await self._flush_samples(buffer)
                    buffer.clear()
                continue

            if sample is None:
                break
            buffer.append(sample)
            if len(buffer) >= self._batch_size:
                await self._flush_samples(buffer)
                buffer.clear()

        if buffer:
            await self._flush_samples(buffer)

    async def _flush_samples(self, samples: list[Sample]) -> None:
        await self._send(
            MessageType.SAMPLES,
            {"samples": _samples_to_wire(samples)},
        )

    async def send_phase(self, phase: str) -> None:
        """Notify coordinator of a phase transition.

        Parameters
        ----------
        phase : str
            Phase name.
        """
        await self._send(MessageType.PHASE, {"phase": phase})

    async def send_heartbeat(self, active_vus: int, iteration_count: int) -> None:
        """Send a heartbeat response.

        Parameters
        ----------
        active_vus : int
            Current active VU count.
        iteration_count : int
            Total iterations completed.
        """
        await self._send(
            MessageType.HEARTBEAT_RESP,
            {"active_vus": active_vus, "iteration_count": iteration_count},
        )

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None:
            await self._ws.close()
        if self._session is not None:
            await self._session.close()
