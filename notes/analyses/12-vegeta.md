# vegeta — structural analysis

**Classification:** Go · goroutine (dynamic pool) concurrency · **open-loop** rate scheduling ·
CLI + targets-file, library-first · single-process.
Pinned at [`tsenart/vegeta@v12.13.0`](https://github.com/tsenart/vegeta/tree/v12.13.0).

## Execution engine

A "brain and muscle" split: one ticker goroutine owns pacing while a pool of worker goroutines each
run `for range ticks { results <- hit() }`. When every worker is blocked on slow I/O and the pool is
below `maxWorkers` (default ≈ `MaxUint64`, i.e. FD/memory-bound), the ticker spawns another worker via
a non-blocking `select`/`default` — back-pressure-driven growth with no separate scaler. The request
*schedule* stays fixed; only in-flight concurrency varies.
→ [`lib/attack.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/attack.go)

## Scheduling & pacing

The defining feature. `Pacer` is `Pace(elapsed, hits) -> (wait, stop)` — a pure function of elapsed
time and cumulative count, never of in-flight concurrency. `ConstantPacer` (aliased `Rate`) returns
`wait = 0` to fire immediately when behind schedule (catch-up), else realigns; it guards an `int64`-ns
overflow before multiplying. `Sine`/`Linear` pacers share the shape. This is explicitly the antidote
to coordinated omission.
→ [`lib/pacer.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/pacer.go)

## Request/result data structure

`Result` holds `Seq`, `Timestamp`, `Code`, `Latency`, `BytesOut/In`, `Error`, `Body`, `Method`, `URL`,
`Headers`. `Timestamp = began.Add(time.Since(began))` uses Go's monotonic clock; `Seq` and `Timestamp`
are assigned in one critical section so they share a total order (the plotter relies on it). `End() =
Timestamp + Latency`.
→ [`lib/results.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/results.go)

## Metric & percentile data structure

`Metrics` aggregates streaming: `Add(*Result)` does no division — counters, status tally, error-set
dedup, min/max, and feeds a **t-digest** estimator (compression 100), so percentiles cost constant
memory regardless of request count. `Close()` computes all derived values once (rate, throughput,
p50/p90/p95/p99) — the cheap-Add/expensive-Close split that makes `report -every` live updates cheap.
A separate bucketed `Histogram` exists for explicit bounds.
→ [`lib/metrics.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/metrics.go)

## Connection / transport

A shared `http.Transport` reuses the idle-connection pool; `hit` always drains the body
(`io.Copy(io.Discard, …)`) so keep-alive connections return clean and reusable. DNS caching, TLS
session resumption, `ConnectTo` dst rewrite, and Unix-socket dialing are configurable.
→ [`lib/attack.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/attack.go)

## Distributed / aggregation

None built in — vegeta is single-process and library-first. Results are a stream
(`Result → Encoder → io.Writer`) composable over Unix pipes (`vegeta attack | vegeta report`); the
user composes distribution.
→ [`lib/reporters.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/reporters.go)

## Scenario / user API

A `Targets` file (HTTP or JSON, one request blueprint per entry) or the `Attacker` library with
functional options. No multi-step flow and no built-in assertions — checks are post-processing on the
result stream.
→ [`lib/attack.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/attack.go)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
