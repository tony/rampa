# ADR 007: Target Capabilities and Architecture Aspirations

Status: Proposed
Date: 2026-05-29

## Context

ADRs 001–003 govern *if and how* native code may enter rampa. ADRs 004–006 make the project
measure itself. Neither says what rampa is *for* — the capabilities it should aspire to as a load
testing framework. This ADR records that vision.

It is written clean-slate: it describes the rampa we would aim for if nothing in the current
codebase or its contracts constrained us. It is a north star, not a commitment to rewrite, and it
deliberately decides nothing technical. Each capability below is stated as an aspiration, shown to
be achievable by a concrete exemplar in an existing project, and handed to a named follow-up ADR
where the actual design will be argued.

The aspirations are grounded in a study of production load generators and control planes — locust,
vegeta, hey, wrk, jmeter, goose, and Distributed Load Testing on AWS — and how Python projects
borrow native speed from Rust (polars, pyo3, pydantic-core, cython). The recurring lessons from
that study shape the vision: the per-request path is I/O-bound everywhere, honest measurement
depends on the scheduling model, and every mature tool reduces metrics with a bounded, mergeable
summary.

## Decision

rampa's vision rests on one spine: **a single contract surface, progressively disclosed across
scale, honest about what it measures, Python-first with optional acceleration.** The same semantic
scenario contract a developer runs on a laptop runs at high throughput on one host and across a
distributed fleet, producing comparable results. When execution moves off-host, a driver may require
a portable behavior reference, code bundle, environment spec, and capability check before the run
starts. We name those scales for what they are — **single-process**, **multi-process**, and
**distributed**.

This ADR commits only to the direction and to the evidence that it is achievable. The technical
decisions are the subject of the follow-up ADRs named throughout.

## Scope

This ADR is the product vision and the roadmap of follow-up ADRs. It explicitly does **not** decide
any mechanism (see *Deferred to follow-up ADRs*). It applies to rampa as a whole; it supersedes no
existing behavior on its own.

## Aspirations

### 1. Progressive disclosure of scale

A load test should be trivial to run on a laptop and scale by preserving the same semantic scenario
contract on a high-throughput single host and then across a distributed fleet, with results that
remain comparable across all three. The user names the scale (single-process, multi-process,
distributed); scenario behavior, metrics, and thresholds retain the same meaning. Remote or
distributed execution may still require a portable behavior reference, code bundle, environment
spec, and capability check before the run starts.

Achievable: locust runs the same user classes in a single process or across a ZeroMQ master/worker
fleet — see [`locust/runners.py`](https://github.com/locustio/locust/blob/2.44.0/locust/runners.py).
Distributed Load Testing on AWS fans task-runner containers through a Step Functions control plane
and task definition, showing the cloud-fleet shape without changing the scenario owner
([`step-functions.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/infrastructure/lib/back-end/step-functions.ts),
[`task-definition.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/task-runner/src/task-definition.ts)).

→ Follow-up ADR: scale modes (single-process / multi-process / distributed).

### 2. Measurement integrity under load

The numbers must stay honest when the target is overloaded — the moment they matter most. For
offered-load tests, that means open-loop arrival modeling, monotonic timing, recording
scheduled-versus-actual start time, and resistance to coordinated omission, so a slow target
reduces neither the offered load nor the reported tail latency silently. Closed-loop VU journeys
remain first-class when the desired model is user-journey throughput rather than an external
arrival process; rampa must distinguish the modes instead of blurring their semantics.

Achievable: vegeta's pacer fires on a schedule independent of in-flight latency and catches up when
behind — see [`lib/pacer.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/pacer.go); wrk
records latency in a monotonic histogram with an explicit coordinated-omission correction pass in
[`src/stats.c`](https://github.com/wg/wrk/blob/4.2.0/src/stats.c). jmeter having to bolt on an
open-model thread group years later is the cautionary counter-example.

→ Follow-up ADR: execution & scheduling model.

### 3. Multi-protocol behind one contract

HTTP/1.1 and HTTP/2, WebSocket, and gRPC should share one scenario API, one metric vocabulary, and
one threshold language. A user learns the contract once; protocols are pluggable engines beneath it.

Achievable: jmeter keeps protocol-specific samplers behind one test-plan and result contract:
HTTP, TCP, and Java samplers live in separate protocol modules, while common assertions operate on
their sample results
([`HTTPSamplerBase.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/http/src/main/java/org/apache/jmeter/protocol/http/sampler/HTTPSamplerBase.java),
[`TCPSampler.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/tcp/src/main/java/org/apache/jmeter/protocol/tcp/sampler/TCPSampler.java),
[`JavaSampler.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/java/src/main/java/org/apache/jmeter/protocol/java/sampler/JavaSampler.java),
[`ResponseAssertion.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/assertions/ResponseAssertion.java)).

→ Follow-up ADR: protocol client engines.

### 4. Scenarios authored in real Python, with a declarative subset

Power users write scenarios as ordinary (async) Python; a declarative subset — targets, steps,
checks — covers the common case, travels well, and is the only thing a future faster execution mode
must understand. Arbitrary Python always runs in Python.

Achievable: locust scenarios are plain Python classes and weighted tasks — see
[`locust/user/task.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/task.py);
jmeter's sampler tree shows the declarative counterpart: a portable plan can name protocol
elements without embedding arbitrary runtime code.

→ Follow-up ADR: scenario API and the native execution mode (under ADR 003).

### 5. Pass/fail as a first-class product

A load test should answer "did it pass?", not just "how fast was it?". Per-request checks (status,
header, body shape) and post-aggregate SLO thresholds (`p99 < 500ms`, `error_rate < 1%`) drive an
abort decision and a CI exit code.

Achievable: jmeter turns checks into assertion results attached to samples, giving the runner a
first-class pass/fail signal to aggregate and report
([`ResponseAssertion.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/assertions/ResponseAssertion.java)).

→ Follow-up ADR: checks & thresholds.

### 6. Metrics you can trust and merge

Latency aggregates must hold in bounded memory regardless of run length, merge correctly across
workers (combine summaries, never average percentiles), and mean the same thing at every scale.

Achievable: vegeta keeps percentiles in a constant-memory t-digest — see
[`lib/metrics.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/metrics.go); locust merges
worker stats by summing histograms and computing percentiles after the merge in
[`locust/stats.py`](https://github.com/locustio/locust/blob/2.44.0/locust/stats.py).

→ Follow-up ADR: metric engine & storage.

### 7. Observability and outputs by default

Results should reach a human and a machine without ceremony: a console summary, JSON, CSV, and HTML
out of the box, plus streaming to OpenTelemetry, Prometheus, InfluxDB, and Datadog — all off the
measurement hot path.

Achievable: jmeter streams live metrics through an asynchronous backend-listener queue to
Graphite/InfluxDB without slowing the samplers — see
[`.../visualizers/backend/BackendListener.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/visualizers/backend/BackendListener.java).

→ Follow-up ADR: outputs & exporters.

### 8. Python-first, optionally Rust-accelerated, never at the cost of integrity

The pure-Python implementation installs and runs anywhere and is the source of truth. Rust earns
its place only at measured, coarse boundaries, releasing the interpreter during heavy native work,
and never changing what a load test measures.

Achievable: polars has Python build a declarative plan and Rust execute it, releasing the GIL during
the compute, through a thin binding crate —
[`crates/polars-python/src/lazyframe/general.rs`](https://github.com/pola-rs/polars/blob/rs-0.53.0/crates/polars-python/src/lazyframe/general.rs);
cython's discipline is to compile only what profiling proves hot, never changing semantics — see its
[compilation guide](https://github.com/cython/cython/blob/3.2.5/docs/src/userguide/source_files_and_compilation.rst);
goose shows a load generator built natively end-to-end in
[`goose@0.18.1`](https://github.com/tag1consulting/goose/blob/0.18.1/src/lib.rs).

→ Follow-up ADR: Rust acceleration map (building on ADR 002 and ADR 003).

### 9. A framework that measures itself

Self-harnessing, self-benchmarking, and self-profiling are part of the product, not an afterthought.
This is already specified — see ADR 004, ADR 005, and ADR 006 — and is named here only to place it
within the vision.

## Roadmap

The aspirations map to a proposed sequence of follow-up ADRs. The numbering is indicative, not a
commitment to order or scope.

| Aspiration | Lead exemplar | Covered feature areas | Follow-up ADR (proposed) |
|---|---|---|---|
| 1 Progressive scale | locust, Distributed Load Testing on AWS | single-process, multi-process, distributed execution | scale modes |
| 2 Measurement integrity | vegeta, wrk | open-loop scheduling, drift, coordinated omission, monotonic timing | execution & scheduling model |
| 3 Multi-protocol contract | jmeter | HTTP, WebSocket, gRPC, custom clients | protocol client engines |
| 4 Python + declarative subset | locust, jmeter | async Python scenarios, setup/teardown data, declarative native subset | scenario API + native execution mode |
| 5 Pass/fail product | jmeter | checks, thresholds, CI exit codes | checks & thresholds |
| 6 Mergeable metrics | vegeta, locust | counters, rates, trends, mergeable summaries, storage layout | metric engine & storage |
| 7 Observability / outputs | jmeter | console, JSON/CSV artifacts, GitHub Actions, InfluxDB, Prometheus, OTEL, webhook | outputs & exporters |
| 8 Python-first + optional Rust | polars, cython | accelerator, engine, worker boundaries | Rust acceleration map |

## Deferred to follow-up ADRs

ADR 007 intentionally decides none of the following. They belong to the ADRs above:

- the scheduler internals (open-loop pacing function, closed-loop executors, drift handling);
- the metric engine's data structures and the exact-versus-approximate percentile choice;
- the distributed coordinator/worker protocol and serialization;
- the per-protocol connection and timing accounting;
- the sample data model and storage layout;
- the specific Rust boundary placements and their shapes (accelerator / engine / worker).

ADR 007 commits to the *direction* and shows, with exemplars, that it is achievable.

## Consequences

### Positive

- Gives the project and its contributors a shared, concrete picture of what rampa is for.
- Anchors each capability to a working example, so the vision is demonstrably achievable, not
  speculative.
- Sequences the design work into named, scoped follow-up ADRs instead of one monolithic redesign.
- Keeps the hard technical choices open and explicit rather than implied by today's code.

### Tradeoffs

- A vision ADR carries no mechanism; on its own it changes nothing in the product.
- Naming follow-up ADRs creates an expectation to write them.

### Risks

- Aspirations without follow-through. Mitigation: the roadmap names each follow-up ADR, and ADRs
  001–006 already establish the disciplines those ADRs must satisfy.
- Scope drift between the vision and what gets built. Mitigation: each follow-up ADR cites the
  aspiration it serves, and the progressive-disclosure invariant (comparable results across scales)
  is a testable constraint per ADR 003.

## Relationship to ADR 001–006

ADR 001–003 govern whether and how native code enters and forbid it from changing what a load test
measures. ADR 004–006 make the project test, benchmark, and profile itself. ADR 007 states what
rampa is for; those ADRs are the disciplines that keep the vision honest, and the follow-up ADRs
named here make it concrete.

## Final position

rampa aspires to be simple enough to run on a laptop and trustworthy enough to run a fleet, across
HTTP, WebSocket, and gRPC, with one contract and honest measurement — Python-first, accelerated by
Rust only where measurement proves it earns its place. This ADR fixes that direction; the ADRs it
names will decide how.

## Prior art

- **locust** (`locustio/locust@2.44.0`) — progressive single-process → master/worker scale, Python
  scenarios, mergeable stats:
  [`locust/runners.py`](https://github.com/locustio/locust/blob/2.44.0/locust/runners.py),
  [`locust/user/task.py`](https://github.com/locustio/locust/blob/2.44.0/locust/user/task.py),
  [`locust/stats.py`](https://github.com/locustio/locust/blob/2.44.0/locust/stats.py).
- **vegeta** (`tsenart/vegeta@v12.13.0`) — open-loop pacer (measurement integrity) and constant-
  memory t-digest metrics:
  [`lib/pacer.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/pacer.go),
  [`lib/metrics.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/metrics.go).
- **wrk** (`wg/wrk@4.2.0`) — monotonic histogram with coordinated-omission correction:
  [`src/stats.c`](https://github.com/wg/wrk/blob/4.2.0/src/stats.c).
- **hey** (`rakyll/hey@v0.1.5`) — minimal closed-loop worker pool (the simple baseline / contrast):
  [`requester/requester.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/requester.go).
- **jmeter** (`apache/jmeter@rel/v5.6.3`) — protocol samplers, assertions, and off-hot-path
  streaming metrics:
  [`protocol/http/.../HTTPSamplerBase.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/http/src/main/java/org/apache/jmeter/protocol/http/sampler/HTTPSamplerBase.java),
  [`protocol/tcp/.../TCPSampler.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/tcp/src/main/java/org/apache/jmeter/protocol/tcp/sampler/TCPSampler.java),
  [`protocol/java/.../JavaSampler.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/protocol/java/src/main/java/org/apache/jmeter/protocol/java/sampler/JavaSampler.java),
  [`assertions/ResponseAssertion.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/assertions/ResponseAssertion.java),
  [`visualizers/backend/BackendListener.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/components/src/main/java/org/apache/jmeter/visualizers/backend/BackendListener.java).
- **Distributed Load Testing on AWS** (`aws-solutions/distributed-load-testing-on-aws@v4.1.0`) —
  cloud control plane and task-runner fan-out:
  [`step-functions.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/infrastructure/lib/back-end/step-functions.ts),
  [`task-definition.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/task-runner/src/task-definition.ts).
- **polars** (`pola-rs/polars@rs-0.53.0`) — Python builds a plan, Rust executes it with the GIL
  released, behind a thin binding:
  [`crates/polars-python/src/lazyframe/general.rs`](https://github.com/pola-rs/polars/blob/rs-0.53.0/crates/polars-python/src/lazyframe/general.rs).
- **pyo3** (`PyO3/pyo3@v0.28.3`) — the thin Python↔Rust binding layer:
  [`src/lib.rs`](https://github.com/PyO3/pyo3/blob/v0.28.3/src/lib.rs).
- **cython** (`cython/cython@3.2.5`) — compile only what profiling proves hot, never changing
  semantics:
  [compilation guide](https://github.com/cython/cython/blob/3.2.5/docs/src/userguide/source_files_and_compilation.rst).
- **goose** (`tag1consulting/goose@0.18.1`) — a load generator built natively end-to-end:
  [`src/lib.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/lib.rs).
