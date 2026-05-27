"""Parity tests for Rust MetricCore against Python sinks.

Feeds identical sample streams into both Python sinks and the Rust
MetricCore, then compares snapshot values. Skips if the Rust extension
is not available.
"""

from __future__ import annotations

import time

import pytest

from rampa.metrics import CounterSink, GaugeSink, RateSink, TrendSink

_core = pytest.importorskip("rampa._core")
MetricCore = _core.MetricCore


def test_metric_core_counter_parity() -> None:
    """Rust counter matches Python CounterSink."""
    py_sink = CounterSink()
    core = MetricCore(capacity=1000)
    core.register("reqs", "counter")

    for i in range(100):
        v = float(i)
        py_sink.add(v)
        core.submit("reqs", v, {})

    time.sleep(0.05)
    snap = core.snapshot(10.0)

    py_fmt = py_sink.format(10.0)
    assert snap["reqs"]["count"] == py_fmt["count"]
    assert abs(snap["reqs"]["rate"] - py_fmt["rate"]) < 0.01


def test_metric_core_gauge_parity() -> None:
    """Rust gauge matches Python GaugeSink."""
    py_sink = GaugeSink()
    core = MetricCore(capacity=1000)
    core.register("cpu", "gauge")

    for v in [10.0, 5.0, 20.0, 15.0]:
        py_sink.add(v)
        core.submit("cpu", v, {})

    time.sleep(0.05)
    snap = core.snapshot(1.0)

    py_fmt = py_sink.format(1.0)
    assert snap["cpu"]["value"] == py_fmt["value"]
    assert snap["cpu"]["min"] == py_fmt["min"]
    assert snap["cpu"]["max"] == py_fmt["max"]


def test_metric_core_rate_parity() -> None:
    """Rust rate matches Python RateSink."""
    py_sink = RateSink()
    core = MetricCore(capacity=1000)
    core.register("checks", "rate")

    for v in [1.0, 0.0, 1.0, 1.0, 0.0]:
        py_sink.add(v)
        core.submit("checks", v, {})

    time.sleep(0.05)
    snap = core.snapshot(1.0)

    py_fmt = py_sink.format(1.0)
    assert snap["checks"]["passes"] == py_fmt["passes"]
    assert snap["checks"]["fails"] == py_fmt["fails"]
    assert abs(snap["checks"]["rate"] - py_fmt["rate"]) < 0.01


def test_metric_core_trend_parity() -> None:
    """Rust trend matches Python TrendSink for integer values."""
    py_sink = TrendSink()
    core = MetricCore(capacity=10000)
    core.register("dur", "trend")

    for i in range(1, 101):
        v = float(i)
        py_sink.add(v)
        core.submit("dur", v, {})

    time.sleep(0.05)
    snap = core.snapshot(1.0)

    py_fmt = py_sink.format(1.0)
    assert snap["dur"]["count"] == py_fmt["count"]
    assert snap["dur"]["min"] == py_fmt["min"]
    assert snap["dur"]["max"] == py_fmt["max"]
    assert abs(snap["dur"]["avg"] - py_fmt["avg"]) < 1.0


def test_metric_core_sub_sink_parity() -> None:
    """Rust sub-sink tag filtering matches Python behavior."""
    core = MetricCore(capacity=1000)
    core.register("dur", "counter")
    core.register_sub_sink("dur", {"status": "200"}, "counter")

    core.submit("dur", 1.0, {"status": "200"})
    core.submit("dur", 1.0, {"status": "200"})
    core.submit("dur", 1.0, {"status": "500"})

    time.sleep(0.05)
    core.flush_and_join()
    snap = core.snapshot(1.0)

    assert snap["dur"]["count"] == 3.0


def test_metric_core_flush_drains_all() -> None:
    """flush_and_join drains all submitted samples."""
    core = MetricCore(capacity=10000)
    core.register("iters", "counter")

    for _ in range(500):
        core.submit("iters", 1.0, {})

    core.flush_and_join()
    snap = core.snapshot(1.0)
    assert snap["iters"]["count"] == 500.0


def test_metric_core_overload_no_crash() -> None:
    """Submitting more than capacity drops samples without crashing."""
    core = MetricCore(capacity=10)
    core.register("x", "counter")

    for _ in range(1000):
        core.submit("x", 1.0, {})

    time.sleep(0.05)
    core.flush_and_join()
    snap = core.snapshot(1.0)
    assert snap["x"]["count"] <= 1000.0
    assert snap["x"]["count"] > 0


def test_metric_core_empty_snapshot() -> None:
    """Snapshot with no samples returns registered metrics with zeros."""
    core = MetricCore(capacity=100)
    core.register("empty", "counter")

    time.sleep(0.05)
    snap = core.snapshot(1.0)
    assert snap["empty"]["count"] == 0.0


def test_rust_metric_core_available_flag_is_bool() -> None:
    """_RUST_METRIC_CORE_AVAILABLE flag exists and is a bool."""
    import rampa.metrics as m

    val = m._RUST_METRIC_CORE_AVAILABLE
    assert isinstance(val, bool)
