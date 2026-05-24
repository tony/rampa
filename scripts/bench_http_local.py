#!/usr/bin/env python3
"""Benchmark rampa HTTP overhead against a local aiohttp server.

Measures the overhead rampa adds around HTTP calls by comparing
against a minimal local server.

Configuration via environment variables:

- ``BENCH_RATE``: target request rate (default: 100)
- ``BENCH_DURATION``: seconds to run (default: 2)
- ``BENCH_MAX_VUS``: maximum concurrent VUs (default: 10)

>>> import scripts.bench_http_local
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
from aiohttp import web

from rampa._types import Sample
from rampa.config import ScenarioConfig
from rampa.executors import ExecutionState
from rampa.executors.constant_arrival_rate import ConstantArrivalRateExecutor
from rampa.worker import Worker


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

    >>> _parse_env_float("_MISSING", 2.0)
    2.0
    """
    return float(os.environ.get(name, str(default)))


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

    >>> _parse_env_int("_MISSING", 5)
    5
    """
    return int(os.environ.get(name, str(default)))


async def run_benchmark(
    rate: float,
    duration: float,
    max_vus: int,
) -> dict[str, t.Any]:
    """Run the HTTP overhead benchmark.

    Parameters
    ----------
    rate : float
        Target requests per second.
    duration : float
        Seconds to run.
    max_vus : int
        Maximum concurrent VUs.

    Returns
    -------
    dict[str, Any]
        Benchmark results with HTTP overhead statistics.
    """

    async def _handler(request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_get("/bench", _handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    addr = site._server.sockets[0].getsockname()  # ty: ignore[unresolved-attribute]
    port: int = addr[1]
    url = f"http://127.0.0.1:{port}/bench"

    sq: queue.SimpleQueue[Sample | None] = queue.SimpleQueue()
    durations: list[float] = []

    async def _http_worker(w: object) -> None:
        assert isinstance(w, Worker)
        start = time.monotonic_ns()
        await w.http.get(url)
        elapsed_ms = (time.monotonic_ns() - start) / 1_000_000
        durations.append(elapsed_ms)
        await w.http.close()

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
        worker_fn=_http_worker,
        scenario="bench_http",
    )

    wall_start = time.monotonic()
    await executor.run(state)
    wall_elapsed = time.monotonic() - wall_start

    await runner.cleanup()

    if not durations:
        return {"error": "no requests completed"}

    durations.sort()
    n = len(durations)

    def _p(pct: float) -> float:
        rank = (pct / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return round(durations[lo] + frac * (durations[hi] - durations[lo]), 3)

    return {
        "benchmark": "http_local",
        "config": {
            "rate": rate,
            "duration": duration,
            "max_vus": max_vus,
        },
        "results": {
            "requests": n,
            "wall_seconds": round(wall_elapsed, 3),
            "actual_rate": round(n / wall_elapsed, 1),
            "duration_p50_ms": _p(50),
            "duration_p95_ms": _p(95),
            "duration_p99_ms": _p(99),
            "duration_max_ms": round(durations[-1], 3),
        },
    }


@click.command()
@click.option("--json-output", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--ndjson", is_flag=True, help="Output as NDJSON.")
def main(json_flag: bool, ndjson: bool) -> None:
    """Run the HTTP overhead benchmark."""
    rate = _parse_env_float("BENCH_RATE", 100.0)
    duration = _parse_env_float("BENCH_DURATION", 2.0)
    max_vus = _parse_env_int("BENCH_MAX_VUS", 10)

    result = asyncio.run(run_benchmark(rate, duration, max_vus))

    if json_flag or ndjson:
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        click.echo("HTTP Local Benchmark")
        click.echo(f"  Rate: {rate}, Duration: {duration}s, MaxVUs: {max_vus}")
        r = result["results"]
        click.echo(f"  Requests: {r['requests']}")
        click.echo(f"  Actual rate: {r['actual_rate']} req/s")
        click.echo(f"  Duration p50: {r['duration_p50_ms']}ms")
        click.echo(f"  Duration p95: {r['duration_p95_ms']}ms")
        click.echo(f"  Duration p99: {r['duration_p99_ms']}ms")


if __name__ == "__main__":
    main()
