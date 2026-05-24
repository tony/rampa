#!/usr/bin/env python3
"""Benchmark arrival-rate scheduling precision.

Measures how closely the constant-arrival-rate executor matches the
target inter-arrival interval using a no-op worker (no HTTP, no I/O).

Configuration via environment variables:

- ``BENCH_RATE``: target iterations per second (default: 1000)
- ``BENCH_DURATION``: seconds to run (default: 2)
- ``BENCH_MAX_VUS``: maximum concurrent VUs (default: 100)

>>> import scripts.bench_scheduler
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import statistics
import sys
import time
import typing as t

import click

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.constant_arrival_rate import ConstantArrivalRateExecutor


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

    >>> os.environ.pop("_TEST_INT", None)
    >>> _parse_env_int("_TEST_INT", 42)
    42
    """
    return int(os.environ.get(name, str(default)))


def _parse_env_float(name: str, default: float) -> float:
    """Parse a float from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : float
        Default value if not set.

    Returns
    -------
    float
        Parsed value.

    >>> os.environ.pop("_TEST_FLOAT", None)
    >>> _parse_env_float("_TEST_FLOAT", 3.14)
    3.14
    """
    return float(os.environ.get(name, str(default)))


def _percentile(data: list[float], p: float) -> float:
    """Compute a percentile using linear interpolation.

    Parameters
    ----------
    data : list[float]
        Sorted values.
    p : float
        Percentile in [0, 100].

    Returns
    -------
    float
        Interpolated percentile value.

    >>> _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50)
    3.0
    """
    if not data:
        return 0.0
    n = len(data)
    if n == 1:
        return data[0]
    rank = (p / 100.0) * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    frac = rank - lower
    return data[lower] + frac * (data[upper] - data[lower])


async def run_benchmark(
    rate: float,
    duration: float,
    max_vus: int,
) -> dict[str, t.Any]:
    """Run the scheduler precision benchmark.

    Parameters
    ----------
    rate : float
        Target iterations per second.
    duration : float
        Seconds to run.
    max_vus : int
        Maximum concurrent VUs.

    Returns
    -------
    dict[str, Any]
        Benchmark results with timing statistics.
    """
    timestamps: list[int] = []

    async def _record_time(w: object) -> None:
        timestamps.append(time.monotonic_ns())

    import datetime

    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    cfg = ScenarioConfig(
        executor="constant-arrival-rate",
        rate=rate,
        duration=datetime.timedelta(seconds=duration),
        max_vus=max_vus,
    )
    executor = ConstantArrivalRateExecutor(cfg)
    state = ExecutionState(
        sample_queue=sq,
        abort_event=asyncio.Event(),
        worker_fn=_record_time,
        scenario="bench",
    )

    wall_start = time.monotonic()
    await executor.run(state)
    wall_elapsed = time.monotonic() - wall_start

    if len(timestamps) < 2:
        return {
            "error": "too few iterations",
            "iterations": len(timestamps),
        }

    intervals_ns = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
    intervals_us = [ns / 1000.0 for ns in intervals_ns]
    target_us = 1_000_000.0 / rate
    drifts_us = [abs(iv - target_us) for iv in intervals_us]
    drifts_us_sorted = sorted(drifts_us)

    return {
        "benchmark": "scheduler_precision",
        "config": {
            "rate": rate,
            "duration": duration,
            "max_vus": max_vus,
        },
        "results": {
            "iterations": len(timestamps),
            "wall_seconds": round(wall_elapsed, 3),
            "actual_rate": round(len(timestamps) / wall_elapsed, 1),
            "target_interval_us": round(target_us, 2),
            "mean_interval_us": round(statistics.mean(intervals_us), 2),
            "stddev_interval_us": round(statistics.stdev(intervals_us), 2)
            if len(intervals_us) > 1
            else 0.0,
            "drift_p50_us": round(_percentile(drifts_us_sorted, 50), 2),
            "drift_p90_us": round(_percentile(drifts_us_sorted, 90), 2),
            "drift_p99_us": round(_percentile(drifts_us_sorted, 99), 2),
            "max_drift_us": round(max(drifts_us), 2),
        },
    }


@click.command()
@click.option(
    "--json-output",
    "json_flag",
    is_flag=True,
    default=False,
    help="Output as JSON.",
)
@click.option(
    "--ndjson",
    is_flag=True,
    default=False,
    help="Output as newline-delimited JSON.",
)
def main(json_flag: bool, ndjson: bool) -> None:
    """Run the scheduler precision benchmark."""
    rate = _parse_env_float("BENCH_RATE", 1000.0)
    duration = _parse_env_float("BENCH_DURATION", 2.0)
    max_vus = _parse_env_int("BENCH_MAX_VUS", 100)

    result = asyncio.run(run_benchmark(rate, duration, max_vus))

    if json_flag or ndjson:
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        click.echo("Scheduler Precision Benchmark")
        click.echo(f"  Rate: {rate} iter/s, Duration: {duration}s, MaxVUs: {max_vus}")
        click.echo(f"  Iterations: {result['results']['iterations']}")
        click.echo(f"  Actual rate: {result['results']['actual_rate']} iter/s")
        click.echo(f"  Target interval: {result['results']['target_interval_us']}us")
        click.echo(f"  Mean interval: {result['results']['mean_interval_us']}us")
        click.echo(f"  Drift p50: {result['results']['drift_p50_us']}us")
        click.echo(f"  Drift p90: {result['results']['drift_p90_us']}us")
        click.echo(f"  Drift p99: {result['results']['drift_p99_us']}us")
        click.echo(f"  Max drift: {result['results']['max_drift_us']}us")


if __name__ == "__main__":
    main()
