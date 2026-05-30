# Cross-cutting: execution engines & scheduling

Two structural choices — the concurrency model and the scheduling model — determine a load
generator's throughput ceiling and its measurement honesty. They are independent: a tool can be fast
and dishonest, or slower and honest.

## Concurrency engines

| Tool | Model | Unit of concurrency | Engine entry |
|---|---|---|---|
| jmeter | thread-per-VU | one JVM thread + a deep-cloned plan subtree per VU | [`StandardJMeterEngine.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/engine/StandardJMeterEngine.java) |
| locust | greenlet | gevent greenlet, one core, cooperative | [`locust/runners.py`](https://github.com/locustio/locust/blob/2.44.0/locust/runners.py) |
| goose | tokio-task | async task on a work-stealing runtime | [`src/goose.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/goose.rs) |
| vegeta | goroutine (dynamic) | goroutine spawned on back-pressure | [`lib/attack.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/attack.go) |
| hey | goroutine (fixed) | one of `C` goroutines | [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go) |
| wrk | sharded-reactor | a connection slot on one of N epoll loops | [`src/wrk.c`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.c) |
| artillery | event-loop | an async VU on one libuv loop | [`packages/core/lib/runner.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/runner.js) |

**The ceiling.** thread-per-VU (jmeter) is bounded by thread stacks + context-switching at a few
thousand VUs. Every other model makes a blocked VU nearly free (a parked greenlet/goroutine/task or a
connection on a reactor), reaching tens of thousands of VUs or 100k+ req/s on one core/host. Once one
box saturates, the answer is more processes/hosts (see [`22`](22-distributed-and-aggregation.md)) — not
a heavier per-VU unit.

## Scheduling models

| Tool | Loop | Mechanism | Coordinated omission | Scheduler entry |
|---|---|---|---|---|
| vegeta | **open** | `Pace(elapsed, hits) -> (wait, stop)`, catch-up when behind | avoided by design | [`lib/pacer.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/pacer.go) |
| artillery | **open** | arrival phases (rate/ramp/count) | avoided (arrival-driven) | [`packages/core/lib/phases.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/phases.js) |
| wrk | closed (open in wrk2) | event loop fires on completion; `stats_correct` back-fill | corrected after the fact; wrk2 avoids it | [`src/stats.c`](https://github.com/wg/wrk/blob/4.2.0/src/stats.c) |
| goose | closed + throttle | user loop; leaky-bucket throttle + `sleep_minus_drift` | mitigated (cadence detect + backfill) | [`src/util.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/util.rs) |
| locust | closed | `wait_time` between tasks (`constant_pacing` → `wait=max(0, t-run)`) | not corrected (pacing collapses) | [`locust/user/task.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/task.py) |
| hey | closed | fixed pool; optional per-worker QPS ticker | not corrected | [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go) |
| jmeter | closed (open bolted on) | timers; `PreciseThroughputTimer` / `OpenModelThreadGroup` | only in the open model | [`OpenModelThreadGroup.kt`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/kotlin/org/apache/jmeter/threads/openmodel/OpenModelThreadGroup.kt) |

**The honesty axis.** Under overload a closed-loop generator stalls with the target and silently
reduces offered load, so its tail-latency numbers under-report. Open-loop generators keep firing on a
monotonic schedule and record scheduled-vs-actual start, so they *measure* overload instead of hiding
it. The reference implementation is vegeta's pure pacing function (cheap, lock-free, overflow-guarded);
the cautionary tale is jmeter having to add an open model years after the fact.

**Timing.** Every honest tool measures latency on a monotonic clock — `time.perf_counter()` (locust),
`time.Since(began)` (vegeta/hey), `time_us()` (wrk), `Instant` (goose). Wall-clock is reserved for
display labels, never latency.
