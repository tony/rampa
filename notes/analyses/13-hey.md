# hey — structural analysis

**Classification:** Go · goroutine (fixed pool) concurrency · closed-loop scheduling (+ optional
per-worker QPS) · CLI single-request · single-process.
Pinned at [`rakyll/hey@v0.1.5`](https://github.com/rakyll/hey/tree/v0.1.5).

## Execution engine

`Work` holds `C` (concurrency), `N` (total requests), and `QPS`. `runWorkers()` spawns exactly `C`
goroutines; each `runWorker()` runs a blocking loop of `N/C` requests (the integer remainder is
silently dropped). Concurrency is capped at `C`, so if the target slows the whole fleet slows with
it — the closed-loop, coordinated-omission-prone model, in its simplest form.
→ [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go)

## Scheduling & pacing

No schedule model. Optional rate limiting is a per-worker `time.Ticker(1e6/QPS µs)` the worker blocks
on before each request, so the aggregate ceiling is `QPS × C` and rate is coupled to response time —
under overload it cannot catch up. Timing uses a monotonic `now()` seam (abstracted per-OS).
→ [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go)

## Request/result data structure

`result` holds `statusCode`, `err`, `offset` (start relative to t₀), `duration`, and `httptrace`
phase splits: `dnsDuration`, `connDuration`, `reqDuration`, `delayDuration` (TTFB), `resDuration`,
plus `contentLength`.
→ [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go)

## Metric & percentile data structure

Collect-then-sort. A single reporter goroutine drains the results channel into exact running scalar
sums plus per-result latency slices **capped at 1,000,000** (`maxRes`); beyond the cap latencies are
dropped from the distribution while the sums stay exact. `finalize`/`snapshot` then sorts the slices
for percentiles (linear-scan pick) and builds a fixed 10-bucket equal-width histogram. Exact but
O(n) memory up to the cap — no mergeability.
→ [`requester/report.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/report.go)

## Aggregation architecture

Lock-free single-consumer fan-in: many worker goroutines → one buffered channel
(`min(C×1000, maxRes)`) → one reporter goroutine that owns all aggregation state, so no mutex is
needed; the reporter is started before the workers.
→ [`requester/report.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/report.go)

## Connection / transport

A shared `http.Transport` with `MaxIdleConnsPerHost = min(C, 500)`, keep-alive on by default
(`-disable-keepalive` to stress fresh connections), compression toggle, optional proxy, and
`httptrace` for phase timing.
→ [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go)

## Distributed / aggregation

None — single-process by design.

## Scenario / user API

A single canonical `http.Request` assembled from CLI flags (`-m`, `-H`, `-d`, `-a`, `-T`, …). No
multi-step flows, no assertions (only status codes recorded). The minimalist baseline — useful mainly
as a contrast to the open-loop tools.
→ [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
