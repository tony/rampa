"""Tests for the rampa EventBus broadcast pub-sub."""

from __future__ import annotations

import asyncio
import threading
import typing as t

import pytest

from rampa.bus import EventBus
from rampa.events import EngineEvent, PhaseEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_Phase = t.Literal["setup", "execute", "teardown", "complete"]


def _make_phase(phase: _Phase = "setup", run_id: str = "test") -> PhaseEvent:
    return PhaseEvent(run_id=run_id, timestamp_ns=0, phase=phase)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class SingleSubscriberFixture(t.NamedTuple):
    """Test case for single subscriber delivery."""

    test_id: str
    events: list[_Phase]
    expected_count: int


_SINGLE_SUB_FIXTURES: list[SingleSubscriberFixture] = [
    SingleSubscriberFixture(
        test_id="one_event",
        events=["setup"],
        expected_count=1,
    ),
    SingleSubscriberFixture(
        test_id="multiple_events",
        events=["setup", "execute", "teardown", "complete"],
        expected_count=4,
    ),
    SingleSubscriberFixture(
        test_id="no_events",
        events=[],
        expected_count=0,
    ),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(SingleSubscriberFixture._fields),
    _SINGLE_SUB_FIXTURES,
    ids=[f.test_id for f in _SINGLE_SUB_FIXTURES],
)
def test_single_subscriber_receives_events(
    test_id: str,
    events: list[_Phase],
    expected_count: int,
) -> None:
    """Single subscriber receives all published events."""

    async def _run() -> list[EngineEvent]:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=100)
        q = bus.subscribe()

        for phase in events:
            bus.publish(_make_phase(phase))
        bus.publish(None)

        received: list[EngineEvent] = []
        while True:
            event = await q.get()
            if event is None:
                break
            received.append(event)
        bus.unsubscribe(q)
        return received

    result = asyncio.run(_run())
    assert len(result) == expected_count


def test_multiple_subscribers_independent() -> None:
    """Multiple subscribers each receive independent copies."""

    async def _run() -> tuple[list[EngineEvent], list[EngineEvent]]:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=100)
        q1 = bus.subscribe()
        q2 = bus.subscribe()

        bus.publish(_make_phase("setup"))
        bus.publish(_make_phase("execute"))
        bus.publish(None)

        async def _drain(
            q: asyncio.Queue[EngineEvent | None],
        ) -> list[EngineEvent]:
            events: list[EngineEvent] = []
            while True:
                event = await q.get()
                if event is None:
                    break
                events.append(event)
            return events

        r1 = await _drain(q1)
        r2 = await _drain(q2)
        bus.unsubscribe(q1)
        bus.unsubscribe(q2)
        return r1, r2

    r1, r2 = asyncio.run(_run())
    assert len(r1) == 2
    assert len(r2) == 2
    assert r1[0] is r2[0]


def test_slow_subscriber_does_not_block() -> None:
    """Publishing never blocks even when a subscriber queue is full.

    A bus with maxsize=2 receives 5 publishes. The queue saturates at 2
    and the remaining 3 are silently dropped for that subscriber. The
    key invariant: publish() returns immediately regardless.
    """

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=2)
        q = bus.subscribe()

        for _ in range(5):
            bus.publish(_make_phase("setup"))

        assert q.qsize() == 2
        bus.unsubscribe(q)

    asyncio.run(_run())


def test_publish_threadsafe_from_thread() -> None:
    """publish_threadsafe delivers events from a background thread."""

    async def _run() -> list[EngineEvent]:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=100)
        q = bus.subscribe()

        def _bg() -> None:
            bus.publish_threadsafe(_make_phase("setup"))
            bus.publish_threadsafe(_make_phase("complete"))
            bus.publish_threadsafe(None)

        thread = threading.Thread(target=_bg)
        thread.start()

        received: list[EngineEvent] = []
        while True:
            event = await q.get()
            if event is None:
                break
            received.append(event)

        thread.join()
        bus.unsubscribe(q)
        return received

    result = asyncio.run(_run())
    assert len(result) == 2


def test_unsubscribe_stops_delivery() -> None:
    """Events published after unsubscribe are not delivered."""

    async def _run() -> int:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=100)
        q = bus.subscribe()

        bus.publish(_make_phase("setup"))
        bus.unsubscribe(q)
        bus.publish(_make_phase("execute"))

        return q.qsize()

    size = asyncio.run(_run())
    assert size == 1


def test_events_iterator() -> None:
    """The events() async iterator yields until None sentinel.

    events() subscribes synchronously at entry (before its first await),
    so the producer task — created second — runs after the subscription
    is active.
    """

    async def _run() -> list[EngineEvent]:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop, maxsize=100)

        async def _consume() -> list[EngineEvent]:
            return [event async for event in bus.events()]

        async def _produce() -> None:
            await asyncio.sleep(0)
            bus.publish(_make_phase("setup"))
            bus.publish(_make_phase("execute"))
            bus.publish(None)

        async with asyncio.TaskGroup() as tg:
            consumer = tg.create_task(_consume())
            tg.create_task(_produce())

        return consumer.result()

    result = asyncio.run(_run())
    assert len(result) == 2


def test_subscriber_count() -> None:
    """subscriber_count tracks subscribe/unsubscribe."""

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        assert bus.subscriber_count == 0

        q1 = bus.subscribe()
        assert bus.subscriber_count == 1

        q2 = bus.subscribe()
        assert bus.subscriber_count == 2

        bus.unsubscribe(q1)
        assert bus.subscriber_count == 1

        bus.unsubscribe(q2)
        assert bus.subscriber_count == 0

    asyncio.run(_run())


def test_double_unsubscribe_safe() -> None:
    """Unsubscribing twice does not raise."""

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        q = bus.subscribe()
        bus.unsubscribe(q)
        bus.unsubscribe(q)

    asyncio.run(_run())
