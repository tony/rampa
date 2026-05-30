# goose — structural analysis

**Classification:** Rust · tokio-task concurrency · closed-loop user loop (+ global request
throttle) · code-first scenarios · single-process.
Pinned at [`tag1consulting/goose@0.18.1`](https://github.com/tag1consulting/goose/tree/0.18.1).

## Execution engine

`GooseAttack` orchestrates the run lifecycle; each virtual user is a `GooseUser` spawned as a tokio
task (`tokio::spawn`) that runs its scenario's transactions in a loop. Because tokio tasks are cheap
and async, one process drives high concurrency on a work-stealing runtime — the Rust analogue of
locust's greenlets, without the GIL.
→ [`src/lib.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/lib.rs),
[`src/goose.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/goose.rs)

## Scheduling & pacing

VU/transaction allocation is a `GooseScheduler` (RoundRobin / Serial / Random). Rate limiting is a
leaky-bucket token broker over a bounded channel — a user must take a token before each request — and
both the throttle and spawn cadence are drift-corrected by `sleep_minus_drift`, which subtracts
elapsed work-time from the intended sleep so pacing does not accumulate drift. Timing is monotonic
`std::time::Instant`; `SystemTime` is used only for wall-clock event labels.
The throttle caps the global request rate; it is not an open-loop arrival scheduler because slow
responses still hold the user loop and reduce realized throughput.
→ [`src/throttle.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/throttle.rs),
[`src/util.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/util.rs)

## Request/result data structure

`GooseRequestMetric` records one request: elapsed (ms, from a monotonic `Instant`), scenario and
transaction index, name, success/error class, status, and the coordinated-omission flag. Latency
resolution is integer milliseconds (`as_millis`).
→ [`src/metrics.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/metrics.rs)

## Metric & percentile data structure

`GooseRequestMetricTimingData` stores response times as a **bucketed histogram**
(`times: BTreeMap<usize, usize>`) with adaptive rounding (no rounding <100 ms, 10 ms to 500 ms,
100 ms to 1 s, 1 s above) to bound memory; percentiles walk the map and clamp to the exact recorded
min/max. Aggregation runs in a dedicated async `MetricsProcessor` task fed by flume channels and
batch-drained — never on the request path. Coordinated omission is mitigated: a cadence detector
(subtracting think-time) flags stalls, and the processor back-fills synthetic samples, kept separate
from the raw distribution.
→ [`src/metrics.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/metrics.rs),
[`src/metrics/coordinated_omission.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/metrics/coordinated_omission.rs)

## Distributed / aggregation

None — goose is single-process (one tokio runtime, a task per VU). Earlier gaggle (worker) support
was dropped; scale-out is left to the operator.

## Scenario / user API

Code-first: a `Scenario` (name, weight, list of transactions) composed of `Transaction`s (name,
weight, async closures over a `GooseUser`). Checks are ordinary Rust over the response. The closest
structural analogue to locust, compiled.
→ [`src/goose.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/goose.rs)

## Source basis

Analysis here is from source at the pinned tag.
