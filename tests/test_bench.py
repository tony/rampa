"""Smoke tests for benchmark scripts.

Each test runs the benchmark with minimal params, verifies JSON output
structure, and confirms the script exits successfully.
"""

from __future__ import annotations

import asyncio
import json
import typing as t

import pytest

from scripts.bench_metrics import run_benchmark as run_metrics
from scripts.bench_scheduler import run_benchmark as run_scheduler
from scripts.bench_throughput import run_benchmark as run_throughput


class BenchSchedulerFixture(t.NamedTuple):
    """Test case for scheduler benchmark."""

    test_id: str
    rate: float
    duration: float
    max_vus: int
    min_iterations: int


_SCHEDULER_FIXTURES: list[BenchSchedulerFixture] = [
    BenchSchedulerFixture(
        test_id="low_rate",
        rate=50.0,
        duration=0.2,
        max_vus=10,
        min_iterations=5,
    ),
]


@pytest.mark.parametrize(
    list(BenchSchedulerFixture._fields),
    _SCHEDULER_FIXTURES,
    ids=[f.test_id for f in _SCHEDULER_FIXTURES],
)
def test_bench_scheduler(
    test_id: str,
    rate: float,
    duration: float,
    max_vus: int,
    min_iterations: int,
) -> None:
    """Scheduler benchmark produces valid JSON with expected fields."""
    result = asyncio.run(run_scheduler(rate, duration, max_vus))
    assert result["benchmark"] == "scheduler_precision"
    assert "config" in result
    assert "results" in result
    r = result["results"]
    assert r["iterations"] >= min_iterations
    assert r["drift_p50_us"] >= 0
    assert r["drift_p99_us"] >= 0
    text = json.dumps(result)
    parsed = json.loads(text)
    assert parsed["benchmark"] == "scheduler_precision"


def test_bench_throughput() -> None:
    """Throughput benchmark produces valid JSON with expected fields."""
    result = asyncio.run(run_throughput(vus=5, duration=0.2))
    assert result["benchmark"] == "throughput"
    assert "results" in result
    r = result["results"]
    assert r["iterations"] > 0
    assert r["samples"] > 0
    assert r["iterations_per_sec"] > 0


def test_bench_metrics_counter() -> None:
    """Metric engine benchmark (counter) produces valid JSON."""
    result = run_metrics(
        total_samples=1000,
        metric_type="counter",
        tag_cardinality=1,
    )
    assert result["benchmark"] == "metric_engine"
    r = result["results"]
    assert r["push_rate"] > 0
    assert r["snapshot_available"] is True


def test_bench_metrics_trend() -> None:
    """Metric engine benchmark (trend) produces valid JSON."""
    result = run_metrics(
        total_samples=1000,
        metric_type="trend",
        tag_cardinality=5,
    )
    assert result["benchmark"] == "metric_engine"
    assert result["results"]["push_rate"] > 0


def test_bench_http_local() -> None:
    """HTTP benchmark produces valid JSON with request stats."""
    from scripts.bench_http_local import run_benchmark as run_http

    result = asyncio.run(run_http(rate=50.0, duration=0.2, max_vus=5))
    assert result["benchmark"] == "http_local"
    r = result["results"]
    assert r["requests"] > 0
    assert r["duration_p50_ms"] > 0
