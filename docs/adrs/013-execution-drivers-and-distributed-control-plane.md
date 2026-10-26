# ADR 013: Execution Drivers and Distributed Control Plane

Status: Proposed
Date: 2026-05-31

## Context

ADR 008 names `ExecutionDriver` as the scale seam. ADR 009 through ADR 012 define attempts,
scheduling, engines, metrics, and aggregation. This ADR decides how those contracts run locally,
across processes, and later on remote workers.

The notes atlas and the distributed-load-testing checkout converge on one structure: a control
plane decides what runs where, data-plane workers execute narrow assignments, and a read model
stores status, history, logs, and artifacts. The useful lesson from cloud systems is lifecycle and
artifact discipline. The metric lesson remains separate: ship summaries, not raw events, and never
average percentiles.

## Decision

rampa exposes one streaming, controllable execution lifecycle across all scale modes:

```python
handle = await rampa.start(plan, scale=rampa.local())
async for event in handle.events():
    ...
await handle.stop("operator requested stop")
result = await handle.wait()
```

`rampa.run(...)` and `rampa.arun(...)` are convenience wrappers over that lifecycle. Local,
process, distributed, and remote drivers consume the same normalized `Plan` and emit the same
result shape.

## Driver Modes

The initial driver vocabulary is:

| Driver | Role |
|---|---|
| `local()` | In-process scheduler, engines, metric summaries, and outputs |
| `processes(n=...)` | Multiple local worker processes behind the same coordinator |
| `distributed(...)` | User-provided workers connected to a coordinator |
| `remote(...)` | Managed remote execution behind pools, regions, queues, or a cloud control plane |

Scale is a driver choice, not a different product. A scenario that runs locally must not need a
different API to run remotely; unsupported behavior references fail preflight.

`remote(...)` is intentionally broader than "one coordinator URL": it may represent managed worker
pools, regional placement, capacity leases, artifact stores, queues, or service-owned scheduling
policy while preserving the same handle, event, summary, and result shape.

## Control, Data, and Read Planes

rampa separates responsibilities:

```text
control plane: normalize plan, validate capabilities, assign segments, coordinate lifecycle
data plane: execute assigned plan segment, emit summaries, artifacts, diagnostics
read model: store status, history, live events, summaries, and artifact references
```

The read model observes and reports. It does not schedule work or sit in the hot measurement path.

## Worker Assignment

A worker receives:

```text
run id
plan version and segment assignment
behavior reference or code bundle reference
environment spec
adapter capability requirements
start barrier configuration
artifact root or upload target
summary protocol version
```

Workers execute the schedule semantics inside their assigned segment using ADR 010's timing model.
They do not invent global load shape or rebalance other workers' work. The driver owns capacity,
assignment, start/stop, retry, and straggler policy; in managed remote mode that driver may delegate
parts of the control plane to a service without changing the public `scale=` contract.

## Remote Lifecycle

Remote execution has explicit phases:

```text
package -> upload -> preflight -> provision -> ready -> start barrier -> run -> drain -> collect -> cleanup
```

The package is a code bundle, importable reference, or declarative behavior subset plus an
environment specification. Workers must run the same code and environment the coordinator records,
or results are not comparable.

Artifacts are uploaded or stored out of band and referenced by URI. Profiles, browser traces, HAR
files, command logs, and heap dumps do not cross the metrics protocol by default.

## Summary Protocol

Workers emit:

```text
capability reports
heartbeats
period summaries
final summaries
artifact references
bounded diagnostics
terminal status
```

They do not emit raw per-attempt streams by default. Period summaries are mergeable under ADR 012.
The coordinator computes aggregate percentiles and thresholds after merge.

Summary metadata can carry segment, worker, region, pool, environment, adapter, and period identity
so enterprise reports can slice results without changing the simple API.

## Failure and Straggler Policy

Worker failure loses or retries only that worker's independent segment. rampa does not import query
engine rollback machinery. The coordinator may reassign a segment, mark it missing, or tolerate it
according to the run policy. Reports include missing or late worker diagnostics.

Cancellation stops new starts, signals workers, drains summaries according to policy, records
terminal status, and runs cleanup. Cleanup failures are reported separately from load-test failures.

## Consequences

### Positive

- The same `Plan` and result shape work locally and remotely.
- Distributed mode has clear lifecycle, capability, placement, and artifact boundaries.
- The coordinator remains merge-focused instead of processing raw events.
- Cloud-style orchestration, managed pools, and regional execution can be added without changing the
  authoring API.

### Tradeoffs

- Remote execution requires packaging and environment specifications.
- Start barriers and heartbeats add protocol work even before managed cloud support exists.
- Debugging raw worker attempts requires explicit diagnostic retention.

## Relationship to Other ADRs

ADR 008 names the driver lifecycle. ADR 009 defines event payloads. ADR 010 defines the scheduling
segments drivers partition. ADR 011 defines engine and adapter capability preflight. ADR 012 defines
the summaries workers send. ADR 014 and ADR 015 use the same driver boundary for browser probes and
project-owned benchmark suites.

## Prior Art Boundary

Distributed Load Testing on AWS (Apache-2.0, `v4.1.0`) is useful as a control-plane reference:
capacity preflight in
[`source/cli/src/lib/scenario-launcher.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/cli/src/lib/scenario-launcher.ts),
Step Functions orchestration in
[`source/infrastructure/lib/back-end/step-functions.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/infrastructure/lib/back-end/step-functions.ts),
worker task construction in
[`source/task-runner/src/task-definition.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/task-runner/src/task-definition.ts),
and artifact reads in
[`source/mcp-server/src/tools/get-test-run-artifacts.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/mcp-server/src/tools/get-test-run-artifacts.ts).
rampa should not copy its percentile aggregation shape; final metrics must follow ADR 012's
merge-first rule.

## Final Position

rampa scales by changing execution drivers, not by changing the user contract. Workers execute
normalized assignments and return summaries plus artifact references; drivers coordinate capacity,
placement, lifecycle, merge, and the read model at whatever scale the selected mode requires.
