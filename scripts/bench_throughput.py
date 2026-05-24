#!/usr/bin/env python3
"""Benchmark maximum iteration throughput with a no-op worker.

Measures how many iterations/sec the engine can sustain with
constant-vus and no protocol overhead.

Configuration via environment variables:

- ``BENCH_VUS``: number of virtual users (default: 50)
- ``BENCH_DURATION``: seconds to run (default: 2)

>>> import scripts.bench_throughput
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import queue
import sys
import time
import typing as t

import click

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.constant_vus import ConstantVUsExecutor


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

    >>> os.environ.pop("_TEST", None)
    >>> _parse_env_int("_TEST", 10)
    10
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

    >>> _parse_env_float("_MISSING", 1.5)
    1.5
    """
    return float(os.environ.get(name, str(default)))


async def run_benchmark(
    vus: int,
    duration: float,
) -> dict[str, t.Any]:
    """Run the throughput benchmark.

    Parameters
    ----------
    vus : int
        Number of virtual users.
    duration : float
        Seconds to run.

    Returns
    -------
    dict[str, Any]
        Benchmark results with throughput statistics.
    """

    async def _noop(w: object) -> None:
        pass

    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    cfg = ScenarioConfig(
        executor="constant-vus",
        vus=vus,
        duration=datetime.timedelta(seconds=duration),
    )
    executor = ConstantVUsExecutor(cfg)
    state = ExecutionState(
        sample_queue=sq,
        abort_event=asyncio.Event(),
        worker_fn=_noop,
        scenario="bench",
    )

    wall_start = time.monotonic()
    await executor.run(state)
    wall_elapsed = time.monotonic() - wall_start

    sample_count = 0
    iteration_count = 0
    while True:
        try:
            s = sq.get_nowait()
        except queue.Empty:
            break
        if s is not None:
            sample_count += 1
            if s.metric == "iterations":
                iteration_count += 1

    return {
        "benchmark": "throughput",
        "config": {
            "vus": vus,
            "duration": duration,
        },
        "results": {
            "iterations": iteration_count,
            "samples": sample_count,
            "wall_seconds": round(wall_elapsed, 3),
            "iterations_per_sec": round(
                iteration_count / wall_elapsed,
                1,
            )
            if wall_elapsed > 0
            else 0.0,
            "samples_per_sec": round(sample_count / wall_elapsed, 1) if wall_elapsed > 0 else 0.0,
        },
    }


@click.command()
@click.option("--json-output", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--ndjson", is_flag=True, help="Output as NDJSON.")
def main(json_flag: bool, ndjson: bool) -> None:
    """Run the throughput benchmark."""
    vus = _parse_env_int("BENCH_VUS", 50)
    duration = _parse_env_float("BENCH_DURATION", 2.0)

    result = asyncio.run(run_benchmark(vus, duration))

    if json_flag or ndjson:
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        click.echo("Throughput Benchmark")
        click.echo(f"  VUs: {vus}, Duration: {duration}s")
        r = result["results"]
        click.echo(f"  Iterations: {r['iterations']}")
        click.echo(f"  Iterations/sec: {r['iterations_per_sec']}")
        click.echo(f"  Samples: {r['samples']}")
        click.echo(f"  Samples/sec: {r['samples_per_sec']}")


if __name__ == "__main__":
    main()
