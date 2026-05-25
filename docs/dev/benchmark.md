(benchmarks)=

# Benchmarks

Four benchmark scripts measure different layers of the framework.
All produce JSON output for CI regression tracking.

## Throughput

Measures raw iterations-per-second with a no-op worker:

```console
$ uv run python scripts/bench_throughput.py
```

Environment variables: `BENCH_VUS` (default 50), `BENCH_DURATION`
(default 2).

## Scheduler precision

Measures arrival-rate scheduling accuracy — how closely actual
inter-arrival times match the target:

```console
$ uv run python scripts/bench_scheduler.py
```

## Metric engine

Measures sample ingestion rate and snapshot latency:

```console
$ uv run python scripts/bench_metrics.py
```

## HTTP overhead

Measures per-request overhead against a local loopback server:

```console
$ uv run python scripts/bench_http_local.py
```

## JSON output

All benchmarks accept `--json-output <path>` to write structured
results for automated comparison:

```console
$ uv run python scripts/bench_throughput.py --json-output bench.json
```
