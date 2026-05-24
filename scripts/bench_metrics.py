#!/usr/bin/env python3
"""Benchmark MetricEngine sample ingestion rate.

Bypasses executors entirely — pushes samples directly into the engine's
queue and measures ingestion throughput and snapshot latency.

Configuration via environment variables:

- ``BENCH_SAMPLES``: total samples to push (default: 100000)
- ``BENCH_METRIC_TYPE``: counter or trend (default: counter)
- ``BENCH_TAG_CARDINALITY``: number of unique tag values (default: 1)

>>> import scripts.bench_metrics
"""

from __future__ import annotations

import json
import os
import queue
import sys
import time
import typing as t

import click

from rampa._types import MetricType, Sample
from rampa.metrics import MetricEngine, MetricRegistry, register_builtins


def _parse_env_int(name: str, default: int) -> int:
    """Parse an integer from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int
        Default value if not set.

    Returns
    -------
    int
        Parsed value.

    >>> _parse_env_int("_MISSING_KEY", 99)
    99
    """
    return int(os.environ.get(name, str(default)))


def run_benchmark(
    total_samples: int,
    metric_type: str,
    tag_cardinality: int,
) -> dict[str, t.Any]:
    """Run the metric engine ingestion benchmark.

    Parameters
    ----------
    total_samples : int
        Number of samples to push.
    metric_type : str
        ``"counter"`` or ``"trend"``.
    tag_cardinality : int
        Number of unique tag values.

    Returns
    -------
    dict[str, Any]
        Benchmark results with ingestion rate and snapshot latency.
    """
    registry = MetricRegistry()
    register_builtins(registry)

    mt = MetricType.COUNTER if metric_type == "counter" else MetricType.TREND
    registry.get_or_create("bench_metric", mt)

    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    engine = MetricEngine(registry=registry, sample_queue=sq)
    engine.start()

    wall_start = time.monotonic()
    for i in range(total_samples):
        tag_val = str(i % tag_cardinality) if tag_cardinality > 1 else "0"
        sq.put(
            Sample(
                "bench_metric",
                float(i),
                time.monotonic_ns(),
                {"tag": tag_val},
            ),
        )
    push_elapsed = time.monotonic() - wall_start

    time.sleep(0.1)

    snap_start = time.monotonic()
    snapshot = engine.get_latest_snapshot()
    snap_elapsed = time.monotonic() - snap_start

    engine.stop()

    return {
        "benchmark": "metric_engine",
        "config": {
            "total_samples": total_samples,
            "metric_type": metric_type,
            "tag_cardinality": tag_cardinality,
        },
        "results": {
            "push_seconds": round(push_elapsed, 4),
            "push_rate": round(total_samples / push_elapsed, 1) if push_elapsed > 0 else 0.0,
            "snapshot_latency_ms": round(snap_elapsed * 1000, 3),
            "snapshot_available": snapshot is not None,
        },
    }


@click.command()
@click.option("--json-output", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--ndjson", is_flag=True, help="Output as NDJSON.")
def main(json_flag: bool, ndjson: bool) -> None:
    """Run the metric engine benchmark."""
    total = _parse_env_int("BENCH_SAMPLES", 100000)
    mt = os.environ.get("BENCH_METRIC_TYPE", "counter")
    card = _parse_env_int("BENCH_TAG_CARDINALITY", 1)

    result = run_benchmark(total, mt, card)

    if json_flag or ndjson:
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        click.echo("Metric Engine Benchmark")
        r = result["results"]
        click.echo(f"  Samples: {total}, Type: {mt}, Tags: {card}")
        click.echo(f"  Push rate: {r['push_rate']} samples/sec")
        click.echo(f"  Push time: {r['push_seconds']}s")
        click.echo(f"  Snapshot latency: {r['snapshot_latency_ms']}ms")


if __name__ == "__main__":
    main()
