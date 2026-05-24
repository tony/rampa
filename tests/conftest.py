"""Shared test helpers for ``rampa``."""

from __future__ import annotations

import queue

import pytest

from rampa._types import Sample


def drain_queue(sq: queue.SimpleQueue[Sample | None]) -> list[Sample]:
    """Drain all samples from a SimpleQueue.

    Parameters
    ----------
    sq : queue.SimpleQueue[Sample | None]
        The queue to drain.

    Returns
    -------
    list[Sample]
        All non-None samples from the queue.
    """
    samples: list[Sample] = []
    while True:
        try:
            s = sq.get_nowait()
        except queue.Empty:
            break
        if s is not None:
            samples.append(s)
    return samples


@pytest.fixture
def sample_queue() -> queue.SimpleQueue[Sample | None]:
    """Provide a fresh SimpleQueue for test sample collection."""
    return queue.SimpleQueue()
