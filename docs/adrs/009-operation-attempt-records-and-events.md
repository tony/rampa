# ADR 009: Operation Attempt Records and Events

Status: Proposed
Date: 2026-05-31

## Context

ADR 008 defines the user-facing `Plan` and says protocol engines emit an operation attempt record
before projecting observations into metrics. That record is the measurement boundary. If it is too
small, rampa cannot later explain failures, retries, browser probes, command adapter exits, or
distributed worker behavior. If it is retained wholesale by default, rampa becomes a raw-event
collector and stops scaling.

The local project patterns point the same way. CLI-heavy projects such as vcspull, libtmux,
libtmux-mcp, tmuxp, and the cihai tools treat duration, exit status, stdout, stderr, timeout, and
traceback handling as part of behavior. Browser profiling adds navigation timing and trace/HAR
artifacts. Distributed load systems add worker identity, assignment identity, and completion state.

This ADR defines the transient event and attempt model every engine reports to rampa. ADR 012
decides how those records become mergeable summaries and thresholds.

## Decision

rampa uses a rich, transient `OperationAttempt` record as the common event payload for work that a
scenario, benchmark target, browser probe, or adapter attempt performs. The record is projected into
metric observations, mergeable summaries, events, diagnostics, and artifact references. Raw attempt
retention is opt-in and bounded.

An operation attempt is not synonymous with an HTTP request. It can represent an HTTP attempt, a
WebSocket message, a gRPC call, a browser navigation, a Python callable benchmark, a pytest slice, a
subprocess invocation, or an external adapter protocol request.

## Record Shape

The normalized attempt record carries these field groups:

```text
identity:      run id, scenario id, operation id, attempt id, adapter/engine id
assignment:    VU id, iteration id, worker id, segment id when present
timing:        scheduled start, actual start, operation start, operation end
outcome:       status, failure class, retry/cancel/timeout flags
protocol:      operation kind, method/action, target, status code or exit code
measurement:   bytes, phase timings, sample values, tags
diagnostics:   bounded messages, stdout/stderr excerpts, error summaries
artifacts:     artifact references, retention reason, media type
```

Every timestamp used for measurement is monotonic and run-relative. Wall-clock timestamps are
metadata for display and correlation only. A worker may report worker-local run-relative times; a
coordinator does not pretend monotonic clocks from separate hosts are comparable.

## Failure Taxonomy

Failures are classified before they reach metrics:

| Class | Meaning |
|---|---|
| `ok` | Attempt completed successfully |
| `check_failed` | User-visible assertion failed but the attempt completed |
| `protocol_error` | Protocol returned an error response or invalid state |
| `timeout` | rampa or adapter timeout elapsed |
| `cancelled` | Run or attempt was cancelled cooperatively |
| `adapter_error` | Adapter protocol, tool, or runtime failed |
| `subprocess_error` | Command could not start or exited unexpectedly |
| `scenario_error` | User scenario code raised outside a managed check |
| `setup_error` | Preflight, server startup, capability, or environment setup failed |
| `internal_error` | rampa invariant failed |

The taxonomy is stable enough for thresholds and reports. Engine-specific diagnostics can add
detail, but they do not replace the top-level class.

## Event Stream

Execution drivers emit a small event stream around attempts:

```text
run.started
scenario.started
operation.scheduled
operation.started
operation.completed
operation.failed
artifact.recorded
summary.period
threshold.evaluated
run.completed
run.failed
```

Events are for observation and control. They are not the aggregate source of truth in distributed
mode. Workers emit bounded summaries for aggregation, and events carry references to those summaries
or artifacts.

## Retention and Artifacts

Raw attempts are normally projected and discarded. Retention modes are explicit:

- failure exemplars;
- slowest-N attempts;
- sampled attempts;
- full debug traces for a bounded local run.

Large payloads, stdout/stderr streams, profiles, browser traces, HAR files, screenshots, videos,
heap dumps, and command logs are artifact references, not inline event payloads. The artifact
record names kind, media type, path or remote URI, attempt id, retention reason, and whether the
content is safe to display inline.

## Consequences

### Positive

- One record explains HTTP, browser, subprocess, pytest, and external adapter attempts.
- Metrics can stay cheap because raw attempts are not the default storage path.
- Failures are comparable across local and distributed drivers.
- Artifacts and diagnostics become first-class without bloating metric messages.

### Tradeoffs

- Engines must map their native failures into rampa's taxonomy.
- Debugging full attempt streams requires explicit retention settings.
- The event model is richer than a flat metric sample, so tests must cover projection carefully.

## Relationship to Other ADRs

ADR 008 names the operation attempt record as the measurement boundary. ADR 010 supplies scheduled
and actual start semantics. ADR 011 supplies protocol and adapter engines that produce attempts.
ADR 012 projects attempts into metrics and summaries. ADR 013 decides which events and summaries
cross worker boundaries.

## Final Position

rampa measures work through a transient, normalized operation attempt record. Attempts explain what
happened; metric summaries decide aggregate truth; artifacts carry large evidence out of band.
