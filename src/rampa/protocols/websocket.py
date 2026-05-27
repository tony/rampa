"""WebSocket protocol client with automatic metric emission.

Emits ``ws_sessions``, ``ws_connecting``, ``ws_session_duration``,
``ws_messages_sent``, ``ws_messages_received``, and ``ws_errors`` metrics.

>>> import rampa.protocols.websocket
"""

from __future__ import annotations

import queue
import time
import typing as t

from rampa._types import Sample, make_sample


class WebSocketSession:
    """An active WebSocket connection with metric emission.

    Created by :meth:`WebSocketClient.connect`. Use as an async context
    manager for automatic cleanup.

    >>> import rampa.protocols.websocket
    """

    def __init__(
        self,
        ws: t.Any,
        sample_queue: queue.SimpleQueue[Sample | None],
        tags: dict[str, str],
        connect_start: float,
    ) -> None:
        self._ws = ws
        self._queue = sample_queue
        self._tags = tags
        self._start = time.monotonic()
        connect_ms = (self._start - connect_start) * 1000
        self._queue.put(make_sample("ws_connecting", connect_ms, tags))
        self._queue.put(make_sample("ws_sessions", 1.0, tags))

    async def send(self, data: str | bytes) -> None:
        """Send a message and emit ``ws_messages_sent``.

        Parameters
        ----------
        data : str | bytes
            Message payload.
        """
        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        else:
            await self._ws.send_str(data)
        self._queue.put(make_sample("ws_messages_sent", 1.0, self._tags))

    async def receive(self) -> str | bytes:
        """Receive a message and emit ``ws_messages_received``.

        Returns
        -------
        str | bytes
            The received message.
        """
        msg = await self._ws.receive()
        self._queue.put(make_sample("ws_messages_received", 1.0, self._tags))
        if msg.type in (1, 2):
            return msg.data
        return msg.data

    async def close(self) -> None:
        """Close the WebSocket and emit ``ws_session_duration``."""
        await self._ws.close()
        elapsed_ms = (time.monotonic() - self._start) * 1000
        self._queue.put(
            make_sample("ws_session_duration", elapsed_ms, self._tags),
        )

    async def __aenter__(self) -> WebSocketSession:
        """Enter context manager."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit context manager and close connection."""
        await self.close()


class WebSocketClient:
    """WebSocket client with automatic metric emission.

    Lazily initialized via ``worker.ws``. Uses aiohttp's WebSocket
    client under the hood.

    >>> import rampa.protocols.websocket
    """

    def __init__(
        self,
        sample_queue: queue.SimpleQueue[Sample | None],
        tags: dict[str, str],
    ) -> None:
        self._queue = sample_queue
        self._tags = tags
        self._session: t.Any = None

    async def connect(self, url: str, **kwargs: t.Any) -> WebSocketSession:
        """Open a WebSocket connection.

        Parameters
        ----------
        url : str
            WebSocket URL (``ws://`` or ``wss://``).
        **kwargs : Any
            Additional arguments passed to ``aiohttp.ClientSession.ws_connect``.

        Returns
        -------
        WebSocketSession
            An active WebSocket session.
        """
        import aiohttp

        if self._session is None:
            self._session = aiohttp.ClientSession()

        connect_start = time.monotonic()
        try:
            ws = await self._session.ws_connect(url, **kwargs)
        except Exception:
            self._queue.put(make_sample("ws_errors", 1.0, self._tags))
            raise
        return WebSocketSession(ws, self._queue, self._tags, connect_start)

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
