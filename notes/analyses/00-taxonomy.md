# Taxonomy: types of load testers

A load tester's identity is fixed by four largely-independent axes. The first two set its
*throughput ceiling*; the third sets its *measurement honesty*; the fourth sets its *authoring
ergonomics*. Everything else is detail.

## The four axes

1. **Concurrency model** — how one process holds N in-flight virtual users (VUs)/requests:
   - *thread-per-VU* — one OS/runtime thread per VU (heavy: stack + context-switch cost);
   - *greenlet/coroutine* — cooperative userspace tasks on one core;
   - *goroutine* — cheap M:N tasks over an OS-thread pool;
   - *event-loop* — one reactor multiplexing many connections;
   - *sharded-reactor* — N threads, each its own event loop owning a slice of connections;
   - *tokio-task* — async tasks on a work-stealing runtime.
2. **Scheduling model** — when the next request fires:
   - *closed-loop (VU-driven)* — a VU sends, waits for the response, then sends again; offered load
     falls when the target slows (prone to coordinated omission);
   - *open-loop (arrival-rate)* — requests fire on a schedule independent of in-flight latency;
     honest under overload.
3. **Measurement integrity** — monotonic timing, scheduled-vs-actual start, and whether
   coordinated omission is corrected, hidden, or avoided.
4. **Scripting/authoring** — *code-first* (write real program code), *declarative* (YAML/data),
   *CLI* (flags for a single request), *script-hook* (embedded scripting language).

## The matrix

| Tool | Runtime | Concurrency model | Scheduling | Scripting | Built-in distribution |
|---|---|---|---|---|---|
| locust | Python | greenlet (gevent) | closed-loop VU (+ pacing) | code-first | yes (ZeroMQ master/worker) |
| jmeter | JVM | thread-per-VU | closed-loop (open-model bolted on) | declarative (XML tree) | yes (RMI) |
| k6 | Go + embedded JS | goroutine + per-VU JS runtime | mixed: closed-loop VU executors + **open-loop** arrival-rate executors | code-first JS + declarative options | no (local runner) |
| vegeta | Go | goroutine (dynamic pool) | **open-loop** (pacer) | CLI + targets file / library | no (single-process) |
| hey | Go | goroutine (fixed pool) | closed-loop (+ per-worker QPS) | CLI (single request) | no |
| wrk | C | sharded-reactor (epoll/kqueue) | closed-loop (open-loop in wrk2) | script-hook (LuaJIT) | no |
| artillery | Node | event-loop (libuv) | **open-loop** (arrival phases) | declarative YAML + JS hooks | yes (worker_threads / Lambda / Fargate) |
| goose | Rust | tokio-task | closed-loop (+ global request throttle) | code-first | no (single-process) |

## What the axes imply

- **The concurrency model is the per-box ceiling.** thread-per-VU (jmeter) caps at thousands of
  VUs on memory and context-switching; greenlet/goroutine/event-loop/tokio reach tens of thousands
  to 100k+ req/s on one core/host because a blocked VU is nearly free. This is why every
  high-throughput tool avoids a thread per VU.
- **The scheduling model is the honesty ceiling.** Open-loop tools (vegeta, artillery, k6
  arrival-rate executors, wrk2) keep firing on schedule when the target stalls, so they measure
  overload; closed-loop tools (hey, locust, jmeter classic timers, k6 VU executors) silently back
  off and under-report tail latency. See
  [`20-engines-and-scheduling.md`](20-engines-and-scheduling.md).
- **The per-request path is I/O-bound in all of them.** The CPU that does exist concentrates in
  scheduling, metric reduction, serialization, and TLS — not the request loop. That is the standing
  conclusion across the per-tool docs and the cross-cutting analyses.
- **Distribution is the next ceiling.** When one box saturates, tools either ship aggregated
  summaries to a coordinator (locust, jmeter, artillery) or stay single-process and leave fan-out
  to the user (k6 local runner, vegeta, hey, wrk, goose). See
  [`22-distributed-and-aggregation.md`](22-distributed-and-aggregation.md).
