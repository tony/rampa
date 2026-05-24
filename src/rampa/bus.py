"""Broadcast event bus for multi-consumer event delivery.

The EventBus fans out EngineEvent objects to any number of subscribers.
Each subscriber gets its own bounded asyncio.Queue. Slow consumers are
isolated — a full subscriber queue causes that subscriber's events to be
dropped without blocking the engine.

>>> import rampa.bus
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import typing as t

from rampa.events import EngineEvent


class EventBus:
    """Broadcast pub-sub bus for engine lifecycle events.

    Thread-safety: the subscriber list is protected by a threading.Lock.
    Publishing from the event-loop thread uses ``publish()``. Publishing
    from a background thread (e.g. MetricEngine) uses ``publish_threadsafe()``.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop that owns subscriber queues.
    maxsize : int
        Maximum queue depth per subscriber before events are dropped.

    >>> import asyncio
    >>> loop = asyncio.new_event_loop()
    >>> bus = EventBus(loop, maxsize=100)
    >>> q = bus.subscribe()
    >>> bus.publish(None)
    >>> loop.run_until_complete(q.get()) is None
    True
    >>> bus.unsubscribe(q)
    >>> loop.close()
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        maxsize: int = 10_000,
    ) -> None:
        self._loop = loop
        self._maxsize = maxsize
        self._subscribers: list[asyncio.Queue[EngineEvent | None]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue[EngineEvent | None]:
        """Create a new subscriber queue.

        Returns
        -------
        asyncio.Queue[EngineEvent | None]
            A bounded queue that will receive published events.
        """
        q: asyncio.Queue[EngineEvent | None] = asyncio.Queue(
            maxsize=self._maxsize,
        )
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[EngineEvent | None]) -> None:
        """Remove a subscriber queue.

        Parameters
        ----------
        q : asyncio.Queue[EngineEvent | None]
            The queue to remove from the subscriber list.
        """
        with self._lock, contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    def publish(self, event: EngineEvent | None) -> None:
        """Publish an event from the event-loop thread.

        Fans out to all subscribers. If a subscriber queue is full,
        the event is dropped for that subscriber only.

        Parameters
        ----------
        event : EngineEvent | None
            The event to broadcast. None signals stream end.
        """
        with self._lock:
            for q in self._subscribers:
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(event)

    def publish_threadsafe(self, event: EngineEvent | None) -> None:
        """Publish an event from a non-event-loop thread.

        Routes through ``loop.call_soon_threadsafe`` to ensure
        asyncio.Queue operations run on the correct event loop.

        Parameters
        ----------
        event : EngineEvent | None
            The event to broadcast.
        """
        self._loop.call_soon_threadsafe(self.publish, event)

    @property
    def subscriber_count(self) -> int:
        """Return the current number of subscribers.

        >>> import asyncio
        >>> loop = asyncio.new_event_loop()
        >>> bus = EventBus(loop)
        >>> bus.subscriber_count
        0
        >>> q = bus.subscribe()
        >>> bus.subscriber_count
        1
        >>> bus.unsubscribe(q)
        >>> bus.subscriber_count
        0
        >>> loop.close()
        """
        with self._lock:
            return len(self._subscribers)

    async def events(self) -> t.AsyncIterator[EngineEvent]:
        """Subscribe and yield events until None sentinel.

        Convenience async iterator that handles subscribe/unsubscribe
        lifecycle automatically.

        Yields
        ------
        EngineEvent
            Engine lifecycle events until the run completes.

        >>> import rampa.bus
        """
        q = self.subscribe()
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self.unsubscribe(q)
