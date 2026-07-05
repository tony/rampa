(adr-003-load-testing-native-execution-pitfalls)=

# ADR 003: Load Testing Semantics and Native Execution Pitfalls

Status: Proposed
Date: 2026-05-28

## Context

ADR 001 defines compatibility requirements for drop-in Rust accelerators. ADR 002 defines a
domain-agnostic native-boundary taxonomy: accelerator, engine, and worker. Those ADRs are vanilla
Python/Rust engineering policy.

rampa is a Python load testing framework. Load testing adds constraints that generic native
boundary policy should not carry. The central risk is not only that native code might be hard to
install or that boundary crossings might be too frequent. The central risk is that native code
can change what the test is measuring while appearing to make the product faster.

Load-test correctness depends on timing, scheduling, failure classification, concurrency, and
aggregation semantics. A native path that preserves the shape of the Python API but changes
request start boundaries, timeout accounting, retry classification, percentile computation, or
overload behavior has changed the result. That is a semantic change, not just an implementation
detail.

Two properties of rampa shape the policy.

First, a load generator usually spends much of its per-request path waiting on I/O. The Python
interpreter is not automatically the limiting factor simply because the product is a load tester.
CPU cost exists, but it tends to concentrate in specific places: scheduling, serialization,
parsing, TLS and native networking, metrics recording, histogram reduction, aggregation, and
cross-process coordination. Native code must target measured bottlenecks, not the request loop by
default.

Second, rampa scenarios are Python user code. Arbitrary Python scenario code cannot be run inside
a native hot loop for free. A native worker either calls back into Python frequently, which
reintroduces boundary and interpreter costs, or it refuses to run arbitrary Python, which means
it is no longer running the full Python scenario. A native execution mode is therefore a distinct
execution capability, not a transparent performance toggle.

## Decision

rampa keeps ADR 001 and ADR 002 generic. This ADR adds rampa-specific constraints for native
accelerators, engines, workers, and execution modes that affect load generation, timing, metrics,
or scenario execution.

### Measurement semantics are public behavior

For rampa, measurement semantics are public behavior. Native code must preserve the documented
meaning of these concepts unless a later ADR explicitly defines a different mode:

- scheduled start time;
- actual start time;
- request start;
- request end;
- latency;
- timeout;
- cancellation;
- retry;
- failure classification;
- success classification;
- connection setup accounting;
- TLS handshake accounting;
- request body write accounting;
- response first-byte accounting;
- response body read accounting;
- queueing and backpressure accounting;
- percentile, histogram, and aggregate-statistic semantics.

A native implementation may use approximate numeric reductions only when the tolerance is
documented and tested. Approximation may affect a numeric aggregate within its stated tolerance.
It must not silently change event classification, timing boundaries, timeout meaning, retry
accounting, or whether a request is considered successful.

### Native code must not redefine the scenario language

The Python scenario API remains the default authoring surface. Arbitrary Python scenarios run in
the Python runtime.

A native worker may support only a declarative scenario subset, such as fixed targets, methods,
headers, payloads, rates, ramps, checks, and thresholds. That subset is not a faster way to run
arbitrary rampa scenarios. It is a smaller language inside the product.

A native execution mode is therefore explicit, opt-in, and checked before execution starts.
Unsupported scenario features are rejected before the run. They are not silently delegated to
Python callbacks, partially executed natively, or hidden behind fallback behavior.

A later ADR may approve a wider bridge, such as an embedded interpreter, compiled scenario subset,
plugin ABI, or measured Python-callback bridge. That ADR must include benchmark data, semantic
guarantees, and failure-mode rules for the bridge.

### Do not nativize the request loop by default

The default native target is not the whole request loop. Native code is appropriate only for a
measured bottleneck or platform boundary.

Likely native candidates:

- metrics aggregation;
- histogram and percentile reduction;
- schedule or rate-plan compilation;
- serialization and parsing in a measured hot path;
- native networking internals when Python networking becomes the measured limit;
- worker orchestration when one Python process cannot drive the required scale;
- platform APIs Python cannot reasonably handle directly.

Poor first targets:

- calling Rust once per request to record one metric;
- calling Rust once per request to compute one delay;
- calling Rust once per response event to update one aggregate;
- calling Python from Rust for arbitrary scenario logic inside the hot loop;
- replacing the whole runtime before the Python scenario model has stabilized.

The boundary should move upward to a schedule, batch, buffer, run plan, metric batch, or worker
protocol message.

### Clock and timing policy

rampa timing uses monotonic time for durations. Native code must not mix wall-clock time into
latency, timeout, duration, schedule-drift, or percentile calculations.

Native code that records time must document:

- the clock source;
- the unit;
- the conversion boundary into Python;
- whether timestamps are absolute monotonic readings, relative durations, or wall-clock labels;
- how overflow, precision loss, and serialization are handled.

Wall-clock time may be used for display labels, logs, report metadata, and user-facing calendar
time. It must not define request latency or timeout duration.

### Scheduling semantics

rampa must distinguish scheduled time from actual start time. Scheduled time answers when the
request was intended to begin. Actual start time answers when work actually began. Completion time
answers when the measured operation ended. Native scheduling code must preserve these distinctions
so overload, queueing, drift, and coordinated omission can be analyzed rather than hidden.

A native scheduler or worker must document whether it implements an open-loop or closed-loop
model, how it handles missed schedule slots, and how it reports overload. It must not smooth,
drop, reschedule, or coalesce events in a way that makes the system under test look better without
recording that behavior.

### Timeout, cancellation, and retry semantics

Native networking, worker, or engine code must preserve rampa's documented timeout, cancellation,
and retry semantics. A timeout is not the same as cancellation. A retry is not the same as a new
independent user operation unless the scenario explicitly says so. A connection error, TLS error,
protocol error, deadline timeout, read timeout, write timeout, and user cancellation may all be
different failure classes if the public result model distinguishes them.

Native code must map low-level errors into rampa result errors through a documented mapping.
Native panics, worker crashes, protocol mismatches, and internal Rust errors are operation
failures or process failures, not successful requests and not silent Python fallbacks.

### Connection and protocol accounting

If rampa measures HTTP or another network protocol, native code must document what is inside each
timing interval:

- DNS lookup;
- TCP connect;
- TLS handshake;
- connection-pool wait;
- request serialization;
- request body write;
- response first byte;
- response body read;
- connection reuse;
- redirect handling;
- decompression;
- protocol upgrade or negotiation.

A native path may differ from the Python path only if the difference is explicit in the mode and
represented in the result schema. Silent differences in connection reuse, TLS behavior, redirect
handling, decompression, HTTP version, or proxy behavior can invalidate comparisons.

### Metrics and aggregation semantics

Native metric code must preserve the event model. It may batch, compress, reduce, or aggregate
events only if it does not hide user-visible outcomes.

For every native metric path, tests must cover:

- empty input;
- one event;
- repeated identical events;
- large batches;
- mixed success and failure events;
- timeout and cancellation events;
- out-of-order timestamps, if accepted;
- boundary durations;
- percentile and histogram boundary cases;
- merge associativity where batches are combined;
- Python-vs-native agreement within documented tolerance.

Percentile and histogram behavior must be documented at the level users rely on. If native code
uses a different histogram representation, bucket strategy, interpolation method, or merge
behavior, that is a public semantic decision and must be approved before shipping.

### Worker mode is a product capability, not a fallback

A rampa worker execution mode requires a follow-up ADR that defines:

- the protocol schema;
- protocol versioning;
- capability negotiation;
- supported scenario subset;
- unsupported-feature rejection;
- result schema;
- timing semantics;
- failure semantics;
- cancellation semantics;
- packaging;
- lifecycle management;
- crash handling;
- compatibility tests;
- benchmark scenarios.

The worker must perform capability negotiation before execution. Unsupported features are rejected
before the run starts. A worker must not start a run, discover an unsupported scenario feature
halfway through, and silently switch to Python.

Worker fallback behavior is explicit. Acceptable fallback policies are:

- reject before run;
- run only when the user explicitly selected worker mode and all capabilities match;
- run Python mode only when the user explicitly selected Python mode.

Unacceptable fallback policies are:

- worker failed, so continue in Python without telling the user;
- unsupported callback, so call back into Python inside the hot loop;
- unsupported metric, so omit it;
- unsupported protocol behavior, so approximate it without marking the result.

### Benchmark policy for native load-generation work

Native load-generation changes must benchmark the user-visible path, not just the native function.
Benchmarks must name the baseline and include enough of the runtime path to expose boundary cost,
scheduling behavior, metrics overhead, and reporting cost.

Benchmarks for native execution or worker behavior should include at least:

- a low-latency target that exposes generator overhead;
- a realistic network target that exposes I/O behavior;
- a high-sample-rate metrics path;
- a schedule with increasing load;
- failure, timeout, and cancellation cases;
- Python-only comparison where behavior overlaps;
- native mode comparison where the supported scenario subset applies.

Benchmark claims must not imply arbitrary Python scenarios run natively unless that exact bridge
exists and is tested.

### Result comparability

Python mode and native mode results are comparable only when they share the same documented
measurement semantics. If a native mode uses a different protocol client, connection policy, HTTP
version, timing boundary, timeout model, retry model, or aggregation method, reports must make
that difference visible.

A faster native result is not automatically a better rampa result. If native mode changes the
load shape or hides generator overload, it may be less useful even when it produces more requests
per second.

## Native change record extension for rampa

Any rampa pull request that adds or changes native code affecting load generation, timing,
metrics, scheduling, networking, or execution mode includes this extension in addition to
ADR 002's native change record.

```text
load-test surface:       scenario | schedule | networking | metrics | reporting | worker
measurement semantics:   timing, failure, retry, timeout, cancellation, and aggregation
                         semantics preserved or intentionally changed
clock source:            monotonic | wall clock for display only | other (explain)
timing boundaries:       scheduled/start/end/timeout boundaries documented and tested
failure mapping:         native errors to rampa result errors
scenario support:        full Python | declarative subset | bridge (cite approving ADR)
capability check:        how unsupported scenario features are rejected before run
fallback behavior:       none | explicit user-selected fallback | rejected before run
comparison mode:         Python-vs-native identity | documented tolerance | not comparable
benchmark coverage:      low-latency target | realistic target | metrics stress |
                         schedule stress | failure cases
```

## Consequences

### Positive

- ADR 001 and ADR 002 stay reusable for general Python/Rust engineering.
- rampa-specific correctness lives where reviewers will look for load-test policy.
- Native code cannot silently alter what a load test measures.
- Native worker mode is treated as an explicit product capability.
- Python scenarios remain honest: arbitrary Python runs in Python unless a measured bridge is
  approved.
- Benchmarks must include the runtime path users observe.

### Tradeoffs

- Native load-generation work has a higher review burden than generic native code.
- Worker mode must define a scenario subset and protocol before it ships.
- Some fast native paths may be rejected because their measurement semantics differ from the
  Python path or cannot be made visible.
- Result comparability becomes explicit rather than assumed.

### Risks

Measurement drift: native mode may change timing or classification while preserving API shape.
The mitigation is measurement-semantics review and Python-vs-native comparison tests.

Scenario fork: native mode may become a second language without being admitted as one. The
mitigation is explicit declarative-subset policy and pre-run capability negotiation.

Silent fallback: worker failure may be hidden by Python execution. The mitigation is explicit
fallback policy and rejection-before-run rules.

Coordinated omission: overload may be hidden by rescheduling, dropping, or smoothing events. The
mitigation is scheduled-time vs. actual-start-time accounting and overload reporting.

False benchmark confidence: native microbenchmarks may ignore scheduling, metrics, reporting, and
boundary costs. The mitigation is user-visible-path benchmark requirements.

## Relationship to ADR 001 and ADR 002

ADR 001 remains the rule for drop-in Rust accelerators that replace public Python APIs.

ADR 002 remains the domain-agnostic rule for native boundary shapes: accelerator, engine, and
worker.

This ADR is rampa-specific. It adds measurement, scheduling, scenario, networking, metrics, and
worker-mode constraints for load testing. It does not change ADR 001 or ADR 002; it adds extra
requirements when native code affects load-test behavior.

## Final position

rampa can use Rust where measurement proves a native boundary is worth the cost. It must not use
Rust in a way that changes what a load test means without saying so.

For rampa, native speed is secondary to measurement integrity. A faster run that changes the load
shape, hides overload, narrows scenario semantics, or corrupts timing is not an acceleration of
the Python product. It is a different product and must be treated as one.
