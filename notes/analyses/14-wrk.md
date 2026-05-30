# wrk — structural analysis

**Classification:** C · sharded-reactor concurrency (epoll/kqueue) · closed-loop scheduling
(open-loop in the wrk2 fork) · LuaJIT script-hook · single-process.
Pinned at [`wg/wrk@4.2.0`](https://github.com/wg/wrk/tree/4.2.0).

## Execution engine

`main` spawns `threads` pthreads; each owns a private `aeEventLoop`, a private `lua_State`, and a flat
`connection[connections/threads]` array — shared-nothing. Each worker is an event-driven reactor
(`aeMain` → `aeProcessEvents`), so thousands of connections collapse onto a handful of OS threads and
one box drives very high RPS. The `thread` and `connection` structs live in `wrk.h`.
→ [`src/wrk.c`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.c),
[`src/wrk.h`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.h)

The event loop is the vendored Redis `ae` (epoll/kqueue/select chosen at compile time via `HAVE_*`);
`ae.c` never names a backend, only `aeApi*`.
→ [`src/ae.c`](https://github.com/wg/wrk/blob/4.2.0/src/ae.c),
[`src/ae.h`](https://github.com/wg/wrk/blob/4.2.0/src/ae.h)

## Scheduling & pacing

Closed-loop implicit: a connection fires its next request when the previous response completes; an
optional Lua `delay()` is honored by removing the WRITABLE event and installing a one-shot timer
(never a blocking sleep). There is no rate limiter — throughput is `connections × (1 / latency)`. The
separate **wrk2** fork replaces this with a constant request rate (open-loop) to fix coordinated
omission. Timing uses a monotonic `time_us()`.
→ `delay_request` in [`src/wrk.c`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.c)

## Request/connection data structure

Per connection (in `wrk.h`): non-blocking `fd`, optional SSL, an inline 8 KiB read buffer, an
`http_parser` response-state machine, a `pending` pipeline counter, and a `start` timestamp (µs).
Reconnect reuses the same array slot (O(1), no allocation); the request buffer is built once per
thread and shared. Sockets are a `sock` function-pointer vtable (plain or SSL) so the hot loop is
identical for TLS.
→ [`src/wrk.h`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.h),
[`src/net.h`](https://github.com/wg/wrk/blob/4.2.0/src/net.h)

## Metric & percentile data structure

`stats` is a **direct-indexed histogram**: `data[v]` counts samples whose value is exactly `v`
microseconds, up to `cfg.timeout`. Record is O(1) via `__sync_fetch_and_add` (lock-free; min/max via
CAS), so the per-request cost is one atomic increment. Percentiles are a rank scan after all threads
join. `stats_correct(expected_interval)` back-fills synthetic samples for stalls — wrk's after-the-fact
coordinated-omission correction (wrk2 does it by construction instead).
→ [`src/stats.h`](https://github.com/wg/wrk/blob/4.2.0/src/stats.h),
[`src/stats.c`](https://github.com/wg/wrk/blob/4.2.0/src/stats.c)

## Distributed / aggregation

None — single-process; per-thread private accumulators merged once at join.

## Scenario / user API

Optional LuaJIT hooks (`setup`, `init`, `request`, `response`, `delay`, `done`) over a mutable `wrk`
table. wrk queries the script once at startup (`script_is_static`, `script_want_response`) to decide
how cheap the hot path can be — if no `response` hook exists, response-body parsing and buffers are
skipped entirely. This capability-gating keeps user scripting out of the hot loop unless the scenario
actually needs it.
→ [`src/wrk.c`](https://github.com/wg/wrk/blob/4.2.0/src/wrk.c)

## Source basis

Cross-checked against pre-existing architecture-study notes and the pinned public source links
above.
