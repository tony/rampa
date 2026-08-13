# ADR 011: Protocol and Adapter Engines

Status: Proposed
Date: 2026-05-31

## Context

ADR 008 gives scenarios a small `VU` surface and leaves protocol clients to follow-up work. ADR 009
requires engines to emit normalized operation attempts. ADR 014 and ADR 015 add browser, command,
Python callable, pytest, and external tool use cases. These should not become separate public
systems.

The local Python projects are mostly ordinary Python code wrapped around subprocesses, CLIs,
pytest, and file outputs. Frontend profiling adds Playwright, Chrome, dev servers, and npm. The
right abstraction is an engine/adapter boundary that keeps rampa's public API Pythonic while
letting external runtimes participate through structured protocols.

## Decision

rampa uses engine objects for in-process protocol clients and adapter objects for external or
optional runtimes. Both satisfy one contract:

```text
capability preflight
normalized run request
operation attempts
metric observations
artifact references
diagnostics
cleanup
```

Engines and adapters do not define public rampa behavior. They implement capabilities and report
rampa-shaped results.

The contract does not make every adapter a worker under ADR 002. In-process Python adapters, such as
a Python callable or Playwright Python binding, are ordinary Python capabilities behind the same
preflight and result contract. Child processes, external runtimes, remote executions, and any
adapter with an independent lifecycle are worker-shaped boundaries and must satisfy ADR 002's
worker rules.

## Engine Families

The initial families are:

| Family | Use |
|---|---|
| HTTP engine | `vu.http` request attempts and phase timings |
| WebSocket engine | connection, message, close, and error attempts |
| gRPC engine | unary and streaming operation attempts |
| Python callable adapter | benchmark or task functions imported by object or import path |
| Command adapter | argv-only subprocess invocations with captured diagnostics |
| Pytest adapter | isolated pytest selections with duration/profile/artifact capture |
| Browser adapter | Playwright/Chrome first-paint and trace/HAR work from ADR 014 |
| External protocol adapter | npm, Node, or other runtimes over versioned JSON stdio |

The base package may ship only lightweight built-ins. Optional engines and adapters declare extras
or third-party packages and are discovered through entry points or runtime registration.

## Capability Preflight

Every engine or adapter exposes a descriptor before execution:

```text
name
version
protocol version when external
supported operation kinds
supported metrics and units
supported artifacts
supported capture policies
concurrency limit
required executables, packages, browsers, or environment variables
remote support
```

Plan or suite normalization validates requested operations against this descriptor. Unsupported
features, missing executables, missing browser binaries, import failures, and incompatible protocol
versions are setup failures.

## Command and External Runtime Boundary

Commands are normalized to argv vectors with explicit cwd, environment overlay, stdin policy,
timeout, stdout/stderr policy, and expected exit behavior. Shell strings may be imported from older
project harnesses, but the normalized rampa form is argv.

External adapters use structured JSON requests and responses rather than log scraping. The protocol
is versioned, includes an attempt id and artifact directory, and returns status, metrics,
artifacts, and diagnostics. A crashed adapter is classified as adapter error and keeps bounded
stdout/stderr diagnostics.

## Lifecycle

Engines and adapters follow a narrow lifecycle:

```text
discover -> preflight -> setup -> run attempt(s) -> flush summaries -> cleanup
```

Setup may start local servers, create protocol sessions, or prepare temporary artifact roots, but
long-lived application server lifecycle belongs to rampa's run orchestration, not to a browser or
command adapter. Cleanup must run after cancellation and failure.

## Consequences

### Positive

- Python, subprocess, pytest, browser, and npm cases share one contract.
- Optional tools do not become base runtime dependencies.
- Missing capabilities fail before schedules start.
- Remote execution can reuse the same adapter protocol later.

### Tradeoffs

- Adapter authors must implement capability descriptors and contract tests.
- JSON protocol adapters are more work than shelling out and parsing text.
- Some existing project harnesses need migration from command strings to argv vectors.

## Relationship to Other ADRs

ADR 008 exposes protocol clients on `VU`. ADR 009 defines the attempts engines emit. ADR 010
drives when attempts start. ADR 012 defines metric projection and aggregation. ADR 013 decides how
engines and adapters run when execution leaves the current process. ADR 014 and ADR 015 specialize
this contract for browser profiling and project-owned benchmark suites.

## Final Position

rampa's extension point is not another DSL. It is a capability-checked engine or adapter that
accepts normalized work and returns normalized attempts, metrics, artifacts, and diagnostics.
