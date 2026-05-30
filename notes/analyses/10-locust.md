# locust — structural analysis

**Classification:** Python · greenlet (gevent) concurrency · closed-loop VU scheduling (with
per-user pacing) · code-first scenarios · built-in distribution.
Pinned at [`locustio/locust@2.44.0`](https://github.com/locustio/locust/tree/2.44.0).

## Execution engine

Every VU is a gevent greenlet, cooperatively scheduled on one OS thread; all concurrency rests on
`gevent.monkey.patch_all()` rewriting the stdlib to cooperative I/O at import. One process therefore
saturates one core, and any CPU-bound or non-cooperative call in user code blocks every other VU.
The runner hierarchy — base `Runner`, `LocalRunner`, and the distributed `MasterRunner`/`WorkerRunner`
— owns spawn/stop lifecycle and the spawn-rate/`LoadTestShape` ramp.
→ [`locust/runners.py`](https://github.com/locustio/locust/blob/2.44.0/locust/runners.py)

## Scheduling & pacing

Closed-loop: each greenlet runs `task → wait → task`. Wait strategies are `between`, `constant`,
`constant_pacing`, and `constant_throughput`; `constant_pacing(t)` computes `wait = max(0, t - run_time)`,
so when a task overruns the window the wait collapses to zero and the user never makes up the
requests it would have sent during a slow period — the coordinated-omission signature. Per-request
timing uses `time.perf_counter()` (monotonic).
→ wait strategies in [`locust/user/task.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/task.py)

## Request/result data structure

There is no per-request record retained; a completed request fires the `request` event into a single
`StatsEntry` keyed by `(name, method)` holding running counts, min/max/total, and a response-time
histogram. `ResponseContextManager` wraps the response and decides success/failure on `__exit__`.
→ [`locust/stats.py`](https://github.com/locustio/locust/blob/2.44.0/locust/stats.py),
[`locust/clients.py`](https://github.com/locustio/locust/blob/2.44.0/locust/clients.py)

## Metric & percentile data structure

`StatsEntry` stores response times as a **bucketed histogram** (`{rounded_ms: count}`), rounding
coarser as values grow, so memory is bounded regardless of run length. Percentiles are computed on
demand by walking the histogram from the top (`calculate_response_time_percentile`, O(buckets)) and
are therefore approximate (bucket-quantized). Merging sums per-bucket counts, so percentiles are
computed *after* merge — never averaged. `RequestStats` is the central holder.
→ [`locust/stats.py`](https://github.com/locustio/locust/blob/2.44.0/locust/stats.py)

## Distributed / aggregation

ZeroMQ ROUTER (master) / DEALER (workers). Messages are compact msgpack `Message(type, data, node_id)`.
The master runs **no** users — it only dispatches the spawn plan, merges worker stats (~3 s cadence)
by summing histograms, and tracks liveness via heartbeats. Workers ship aggregated stats, not raw
request events.
→ [`locust/rpc/protocol.py`](https://github.com/locustio/locust/blob/2.44.0/locust/rpc/protocol.py),
master/worker in [`locust/runners.py`](https://github.com/locustio/locust/blob/2.44.0/locust/runners.py)

## Scenario / user API

A scenario is a Python subclass of `User`/`HttpUser` with weighted `@task` methods and a `wait_time`;
`TaskSet` nests tasks into a state machine. Checks are ordinary Python (`assert`, or
`response.failure(...)` on the context manager) — there is no declarative assertion model.
→ [`locust/user/users.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/users.py),
[`locust/user/task.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/task.py),
errors in [`locust/exception.py`](https://github.com/locustio/locust/blob/2.44.0/locust/exception.py)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
