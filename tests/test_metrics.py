"""Tests for rampa metric registry, sinks, and engine."""

from __future__ import annotations

import queue
import time
import typing as t

import pytest

from rampa._types import MetricType, Sample
from rampa.metrics import (
    CounterSink,
    GaugeSink,
    MetricEngine,
    MetricRegistry,
    MetricSnapshot,
    RateSink,
    TrendSink,
    register_builtins,
)


def test_counter_sink_accumulates() -> None:
    """CounterSink tracks running total and rate."""
    s = CounterSink()
    s.add(1.0)
    s.add(2.0)
    s.add(3.0)
    result = s.format(10.0)
    assert result["count"] == 6.0
    assert result["rate"] == pytest.approx(0.6)


def test_counter_sink_zero_duration() -> None:
    """CounterSink handles zero duration without division error."""
    s = CounterSink()
    s.add(5.0)
    result = s.format(0.0)
    assert result["count"] == 5.0
    assert result["rate"] == 0.0


def test_gauge_sink_tracks_latest() -> None:
    """GaugeSink reports latest value and min/max."""
    s = GaugeSink()
    s.add(10.0)
    s.add(5.0)
    s.add(20.0)
    s.add(15.0)
    result = s.format(1.0)
    assert result["value"] == 15.0
    assert result["min"] == 5.0
    assert result["max"] == 20.0


def test_gauge_sink_empty() -> None:
    """GaugeSink returns zeros when no values added."""
    s = GaugeSink()
    result = s.format(1.0)
    assert result["value"] == 0.0
    assert result["min"] == 0.0
    assert result["max"] == 0.0


def test_rate_sink_tracks_passes_fails() -> None:
    """RateSink counts truthy/falsy values correctly."""
    s = RateSink()
    s.add(1.0)
    s.add(1.0)
    s.add(0.0)
    s.add(1.0)
    result = s.format(1.0)
    assert result["passes"] == 3.0
    assert result["fails"] == 1.0
    assert result["rate"] == pytest.approx(0.75)


def test_rate_sink_empty() -> None:
    """RateSink returns zero rate when no values added."""
    s = RateSink()
    result = s.format(1.0)
    assert result["rate"] == 0.0


class PercentileFixture(t.NamedTuple):
    """Test case for TrendSink percentile computation."""

    test_id: str
    values: list[float]
    percentile: float
    expected: float
    tolerance: float


_PERCENTILE_FIXTURES: list[PercentileFixture] = [
    PercentileFixture(
        "p50_odd",
        [1.0, 2.0, 3.0, 4.0, 5.0],
        50,
        3.0,
        0.001,
    ),
    PercentileFixture(
        "p50_even",
        [1.0, 2.0, 3.0, 4.0],
        50,
        2.5,
        0.001,
    ),
    PercentileFixture(
        "p90_100",
        [float(v) for v in range(1, 101)],
        90,
        90.1,
        0.01,
    ),
    PercentileFixture(
        "p95_100",
        [float(v) for v in range(1, 101)],
        95,
        95.05,
        0.01,
    ),
    PercentileFixture(
        "p99_100",
        [float(v) for v in range(1, 101)],
        99,
        99.01,
        0.01,
    ),
    PercentileFixture(
        "p0",
        [10.0, 20.0, 30.0],
        0,
        10.0,
        0.001,
    ),
    PercentileFixture(
        "p100",
        [10.0, 20.0, 30.0],
        100,
        30.0,
        0.001,
    ),
    PercentileFixture(
        "single_value",
        [42.0],
        95,
        42.0,
        0.001,
    ),
]


@pytest.mark.parametrize(
    list(PercentileFixture._fields),
    _PERCENTILE_FIXTURES,
    ids=[f.test_id for f in _PERCENTILE_FIXTURES],
)
def test_trend_percentile(
    test_id: str,
    values: list[float],
    percentile: float,
    expected: float,
    tolerance: float,
) -> None:
    """TrendSink percentile uses linear interpolation."""
    s = TrendSink()
    for v in values:
        s.add(v)
    assert s.percentile(percentile) == pytest.approx(
        expected,
        abs=tolerance,
    )


def test_trend_sink_format() -> None:
    """TrendSink format includes all standard aggregations."""
    s = TrendSink()
    for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
        s.add(v)
    result = s.format(1.0)
    assert result["count"] == 5.0
    assert result["avg"] == 30.0
    assert result["min"] == 10.0
    assert result["max"] == 50.0
    assert "med" in result
    assert "p(90)" in result
    assert "p(95)" in result
    assert "p(99)" in result


def test_trend_sink_empty() -> None:
    """TrendSink returns zeros when no values added."""
    s = TrendSink()
    result = s.format(1.0)
    assert result["count"] == 0.0
    assert result["avg"] == 0.0


def test_registry_create_and_retrieve() -> None:
    """MetricRegistry creates and retrieves metrics by name."""
    reg = MetricRegistry()
    m = reg.get_or_create("reqs", MetricType.COUNTER)
    assert m.name == "reqs"
    assert m.metric_type == MetricType.COUNTER
    m2 = reg.get_or_create("reqs", MetricType.COUNTER)
    assert m is m2


def test_registry_rejects_type_conflict() -> None:
    """MetricRegistry rejects re-registration with different type."""
    reg = MetricRegistry()
    reg.get_or_create("reqs", MetricType.COUNTER)
    with pytest.raises(ValueError, match="already registered"):
        reg.get_or_create("reqs", MetricType.GAUGE)


def test_registry_creates_matching_sinks() -> None:
    """MetricRegistry creates a sink matching the metric type."""
    reg = MetricRegistry()
    reg.get_or_create("dur", MetricType.TREND)
    sink = reg.get_sink("dur")
    assert sink is not None
    assert hasattr(sink, "add")
    assert hasattr(sink, "format")


def test_register_builtins_populates_registry() -> None:
    """register_builtins adds all expected builtin metrics."""
    reg = MetricRegistry()
    register_builtins(reg)
    metrics = reg.all_metrics()
    assert "iterations" in metrics
    assert "dropped_iterations" in metrics
    assert "vus" in metrics
    assert "checks" in metrics
    assert "data_sent" in metrics


def test_metric_engine_drains_samples() -> None:
    """MetricEngine thread ingests samples and produces snapshots."""
    reg = MetricRegistry()
    register_builtins(reg)
    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=reg, sample_queue=q)
    engine.start()

    for _ in range(10):
        q.put(Sample("iterations", 1.0, time.monotonic_ns(), {}))

    time.sleep(0.15)
    engine.stop()

    snap = engine.get_latest_snapshot()
    assert snap is not None
    assert snap.values["iterations"]["count"] == 10.0


def test_metric_engine_snapshots_bounded() -> None:
    """MetricEngine stores at most 128 snapshots (bounded deque)."""
    reg = MetricRegistry()
    register_builtins(reg)
    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=reg, sample_queue=q, flush_interval=0.001)
    engine.start()

    q.put(Sample("iterations", 1.0, time.monotonic_ns(), {}))
    time.sleep(0.15)
    engine.stop()

    assert len(engine._snapshots) <= 128


def test_metric_engine_on_snapshot_callback() -> None:
    """MetricEngine calls on_snapshot with each emitted snapshot."""
    reg = MetricRegistry()
    register_builtins(reg)
    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    received: list[MetricSnapshot] = []
    engine = MetricEngine(
        registry=reg,
        sample_queue=q,
        on_snapshot=received.append,
    )
    engine.start()

    q.put(Sample("iterations", 1.0, time.monotonic_ns(), {}))
    time.sleep(0.15)
    engine.stop()

    assert len(received) > 0
    assert all(isinstance(s, MetricSnapshot) for s in received)


# --- Sub-sink index tests ---


def test_sub_sink_routes_to_correct_metric() -> None:
    """Sub-sinks indexed by base metric receive only matching samples."""
    reg = MetricRegistry()
    reg.get_or_create("http_dur", MetricType.TREND)
    reg.get_or_create("grpc_dur", MetricType.TREND)

    http_sink = reg.get_or_create_sub_sink("http_dur", {"status": "200"})
    grpc_sink = reg.get_or_create_sub_sink("grpc_dur", {"status": "200"})

    assert http_sink is not None
    assert grpc_sink is not None

    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=reg, sample_queue=q)
    engine.start()

    for _ in range(5):
        q.put(Sample("http_dur", 10.0, time.monotonic_ns(), {"status": "200"}))
    time.sleep(0.15)
    engine.stop()

    http_fmt = http_sink.format(1.0)
    grpc_fmt = grpc_sink.format(1.0)
    assert http_fmt["count"] == 5.0
    assert grpc_fmt["count"] == 0.0


def test_sub_sink_overlapping_tags_across_metrics() -> None:
    """Sub-sinks with same tags on different metrics don't cross-contaminate."""
    reg = MetricRegistry()
    reg.get_or_create("metric_a", MetricType.COUNTER)
    reg.get_or_create("metric_b", MetricType.COUNTER)

    sink_a = reg.get_or_create_sub_sink("metric_a", {"env": "prod"})
    sink_b = reg.get_or_create_sub_sink("metric_b", {"env": "prod"})

    assert sink_a is not None
    assert sink_b is not None

    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=reg, sample_queue=q)
    engine.start()

    q.put(Sample("metric_a", 1.0, time.monotonic_ns(), {"env": "prod"}))
    q.put(Sample("metric_a", 1.0, time.monotonic_ns(), {"env": "prod"}))
    q.put(Sample("metric_b", 1.0, time.monotonic_ns(), {"env": "prod"}))
    time.sleep(0.15)
    engine.stop()

    assert sink_a.format(1.0)["count"] == 2.0
    assert sink_b.format(1.0)["count"] == 1.0


def test_sub_sink_multiple_filters_same_metric() -> None:
    """Multiple sub-sinks on the same metric each receive correct samples."""
    reg = MetricRegistry()
    reg.get_or_create("http_dur", MetricType.TREND)

    ok_sink = reg.get_or_create_sub_sink("http_dur", {"status": "200"})
    err_sink = reg.get_or_create_sub_sink("http_dur", {"status": "500"})

    assert ok_sink is not None
    assert err_sink is not None

    q: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=reg, sample_queue=q)
    engine.start()

    for _ in range(3):
        q.put(Sample("http_dur", 10.0, time.monotonic_ns(), {"status": "200"}))
    q.put(Sample("http_dur", 50.0, time.monotonic_ns(), {"status": "500"}))
    time.sleep(0.15)
    engine.stop()

    assert ok_sink.format(1.0)["count"] == 3.0
    assert err_sink.format(1.0)["count"] == 1.0


def test_sub_sinks_for_accessor() -> None:
    """MetricRegistry.sub_sinks_for returns only sub-sinks for that metric."""
    reg = MetricRegistry()
    reg.get_or_create("dur", MetricType.TREND)
    reg.get_or_create("reqs", MetricType.COUNTER)

    reg.get_or_create_sub_sink("dur", {"status": "200"})
    reg.get_or_create_sub_sink("dur", {"status": "500"})
    reg.get_or_create_sub_sink("reqs", {"method": "GET"})

    assert len(reg.sub_sinks_for("dur")) == 2
    assert len(reg.sub_sinks_for("reqs")) == 1
    assert len(reg.sub_sinks_for("nonexistent")) == 0


def test_all_sub_sinks_by_metric() -> None:
    """MetricRegistry.all_sub_sinks_by_metric returns indexed snapshot."""
    reg = MetricRegistry()
    reg.get_or_create("dur", MetricType.TREND)
    reg.get_or_create("reqs", MetricType.COUNTER)

    reg.get_or_create_sub_sink("dur", {"status": "200"})
    reg.get_or_create_sub_sink("reqs", {"method": "GET"})

    by_metric = reg.all_sub_sinks_by_metric()
    assert "dur" in by_metric
    assert "reqs" in by_metric
    assert len(by_metric["dur"]) == 1
    assert len(by_metric["reqs"]) == 1
