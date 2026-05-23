"""Tests for rampa worker checks and custom metrics."""

from __future__ import annotations

import queue

from rampa._types import Sample
from rampa.worker import ExecutionInfo, Worker


def _make_worker() -> tuple[Worker, queue.SimpleQueue[Sample | None]]:
    """Create a worker with a fresh sample queue."""
    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    w = Worker(
        sample_queue=sq,
        execution=ExecutionInfo(worker_id=1, scenario="test", iteration=0),
        setup_data={"token": "abc"},
    )
    return w, sq


def _drain(sq: queue.SimpleQueue[Sample | None]) -> list[Sample]:
    """Drain all samples from a queue."""
    samples: list[Sample] = []
    while True:
        try:
            s = sq.get_nowait()
        except Exception:
            break
        if s is not None:
            samples.append(s)
    return samples


def test_check_all_pass() -> None:
    """check() returns True when all conditions pass."""
    w, sq = _make_worker()
    result = w.check(
        200,
        {
            "is 200": lambda v: v == 200,
            "is int": lambda v: isinstance(v, int),
        },
    )
    assert result is True
    samples = _drain(sq)
    assert len(samples) == 2
    assert all(s.metric == "checks" for s in samples)
    assert all(s.value == 1.0 for s in samples)


def test_check_partial_fail() -> None:
    """check() returns False when any condition fails."""
    w, sq = _make_worker()
    result = w.check(
        404,
        {
            "is 200": lambda v: v == 200,
            "is int": lambda v: isinstance(v, int),
        },
    )
    assert result is False
    samples = _drain(sq)
    values = {s.tags["check"]: s.value for s in samples}
    assert values["is 200"] == 0.0
    assert values["is int"] == 1.0


def test_check_exception_counts_as_fail() -> None:
    """check() treats predicate exceptions as failures."""
    w, sq = _make_worker()

    def _raise(_v: object) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    result = w.check(None, {"exploder": _raise})
    assert result is False
    samples = _drain(sq)
    assert samples[0].value == 0.0


def test_check_tags_include_scenario() -> None:
    """check() samples include the scenario tag."""
    w, sq = _make_worker()
    w.check(True, {"ok": lambda v: v})
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.tags["scenario"] == "test"


def test_counter_emits_sample() -> None:
    """counter() emits a sample with the given value."""
    w, sq = _make_worker()
    w.counter("my_counter", 5.0)
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.metric == "my_counter"
    assert sample.value == 5.0


def test_counter_default_value() -> None:
    """counter() defaults to value 1.0."""
    w, sq = _make_worker()
    w.counter("hits")
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.value == 1.0


def test_gauge_emits_sample() -> None:
    """gauge() emits a sample with the given value."""
    w, sq = _make_worker()
    w.gauge("queue_depth", 42.0)
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.metric == "queue_depth"
    assert sample.value == 42.0


def test_trend_emits_sample() -> None:
    """trend() emits a sample with the given value."""
    w, sq = _make_worker()
    w.trend("latency", 123.4)
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.metric == "latency"
    assert sample.value == 123.4


def test_custom_metric_with_tags() -> None:
    """Custom metric methods pass tags through."""
    w, sq = _make_worker()
    w.counter("reqs", 1.0, tags={"method": "GET"})
    sample = sq.get_nowait()
    assert sample is not None
    assert sample.tags["method"] == "GET"


def test_setup_data_accessible() -> None:
    """Worker exposes setup_data from construction."""
    w, _sq = _make_worker()
    assert w.setup_data == {"token": "abc"}


def test_worker_isolation() -> None:
    """Two workers share a queue but have independent state."""
    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    w1 = Worker(
        sample_queue=sq,
        execution=ExecutionInfo(worker_id=1, scenario="a", iteration=0),
    )
    w2 = Worker(
        sample_queue=sq,
        execution=ExecutionInfo(worker_id=2, scenario="b", iteration=0),
    )
    w1.counter("from_w1")
    w2.counter("from_w2")
    samples = _drain(sq)
    metrics = {s.metric for s in samples}
    assert "from_w1" in metrics
    assert "from_w2" in metrics
    assert w1.execution.worker_id != w2.execution.worker_id
