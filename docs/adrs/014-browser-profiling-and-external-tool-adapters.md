# ADR 014: Browser Profiling and External Tool Adapters

Status: Proposed
Date: 2026-05-31

## Context

ADR 008 defines `Plan` as rampa's normalized authoring contract and leaves event, scheduling,
protocol, metrics, and scale details to ADR 009 through ADR 013. Browser profiling should not take
over those reserved contracts. It is a consumer of them: a browser workload still needs scheduled
and actual start timestamps, operation outcomes, metric samples, artifacts, and capability
validation before a run begins.

The immediate use case is frontend profiling: start or target a local web application, open it in
Chrome or another browser, record first paint and related browser timings, and keep traces or HAR
files when requested. This differs from HTTP load generation. It measures client-side browser work,
not only server response latency, and it may involve tools whose primary runtime is Python, Node,
or another language.

ADR 006 requires profiling to be one command away while preserving measurement integrity. ADR 003
requires timing, timeout, cancellation, and failure classification to remain public behavior. ADR
002 says an independent tool behind a message boundary is a worker-shaped boundary, not an
in-process accelerator. Browser automation may use that shape when rampa invokes a child process,
Chrome, an npm package, or another external runtime. A Python binding adapter remains an in-process
Python capability unless it owns an independent lifecycle.

## Decision

rampa adds a browser-profiling adapter layer instead of making Playwright a required dependency or
embedding one language runtime into the core API. The public rampa API remains Python-first and
small, while browser execution is delegated to adapters that declare capabilities, run in a
controlled lifecycle, and report normalized metrics and artifacts back to rampa.

### Simple profiling surface

The shortest path is an intent-level profiling call:

```python
import rampa

result = rampa.profile.browser(
    "/",
    base_url="http://127.0.0.1:4173",
    server=rampa.command_server(
        ["npm", "run", "dev"],
        ready_url="http://127.0.0.1:4173",
    ),
    metrics=["first_paint", "first_contentful_paint"],
    repeat=3,
    capture=rampa.capture(trace="failure", har="failure"),
)
```

This call normalizes into a browser scenario, `repeat(3)` schedule, adapter request, operation
attempts, metric summaries, and artifact records. Users do not need to construct those lower layers
unless they are composing browser work with other scenarios, thresholds, outputs, or scale modes.

### Adapter boundary

A browser adapter is a capability-checked execution boundary. It may run in the current Python
process through the Playwright Python package, in a child process through an npm package, in another
language runtime, or later inside a remote worker. The result contract is the same either way:

```text
Plan browser behavior
  -> adapter capability preflight
  -> adapter run request
  -> normalized attempt result
  -> rampa metrics, events, artifacts, thresholds
```

The adapter does not define rampa's public behavior. It implements a declared capability set and
must return rampa-shaped results. Missing tools, unsupported browsers, unsupported metrics, protocol
mismatches, startup failures, crashes, and timeouts are reported before or during the run with
stable rampa failure classifications. They are not hidden behind silent fallback to another adapter.

The base package remains installable, importable, and usable without Playwright, Node, npm, or
browser binaries. Browser adapters are optional capabilities.

### Explicit Plan form

When browser profiling is part of a larger load-test or benchmark composition, the same work can be
written as an explicit `Plan`:

```python
import rampa

plan = rampa.Plan(
    scenarios=[
        rampa.Scenario(
            name="home page first paint",
            behavior=rampa.browser(
                "/",
                adapter=rampa.playwright.python(),
                browser="chromium",
                channel="chrome",
                metrics=["first_paint", "first_contentful_paint"],
                capture=rampa.capture(trace="on", har="on"),
            ),
            schedule=rampa.repeat(3),
        ),
    ],
)

result = rampa.run(
    plan,
    base_url="http://127.0.0.1:4173",
    server=rampa.command_server(["npm", "run", "dev"], ready_url="http://127.0.0.1:4173"),
)
```

An npm-backed adapter is explicit, not magic:

```python
plan = rampa.Plan(
    scenarios=[
        rampa.Scenario(
            name="home page first paint",
            behavior=rampa.browser(
                "/",
                adapter=rampa.playwright.node(package="@rampa/playwright-adapter"),
                metrics=["first_paint"],
            ),
            schedule=rampa.repeat(5),
        ),
    ],
)
```

`adapter="auto"` may exist only as normalization sugar. The selected adapter, adapter version,
tool version, browser engine, and capability set are recorded in the normalized run metadata before
execution starts. Once normalized, the run uses that adapter or fails; it does not fall back to a
different language runtime after partial execution.

### Adapter families

rampa supports three adapter families under one contract.

**Python binding adapters.** These use Python packages such as Playwright Python. They are the
most Pythonic local path and can share Python environment management with the rampa run. They are
not worker-shaped unless they own an independent lifecycle. They are still optional extras, and
browser binary installation remains an explicit setup step.

**Command protocol adapters.** These launch an external command such as an npm package, a Node
script, or another language runtime. The command receives a JSON request and emits a versioned JSON
response, preferably over stdio. This is the general extension story for npm packages and other
language ecosystems.

**Remote worker adapters.** These use ADR 013's scale and remote protocol. The browser adapter
contract is intentionally serializable so a remote worker can execute the same browser probe and
return summaries plus artifact references.

The command protocol is the portable boundary for non-Python tooling. It avoids log scraping and
shell-specific parsing. A command adapter receives a request shaped like:

```json
{
  "protocol": "rampa.browser-adapter.v1",
  "attempt_id": "home-page-first-paint/000001",
  "url": "http://127.0.0.1:4173/",
  "browser": "chromium",
  "metrics": ["first_paint"],
  "capture": {"trace": "on", "har": "off"},
  "timeout_ms": 30000,
  "artifact_dir": "artifacts/home-page-first-paint/000001"
}
```

It returns:

```json
{
  "protocol": "rampa.browser-adapter.v1",
  "status": "passed",
  "metrics": {"browser.first_paint": 23.4},
  "artifacts": [
    {"kind": "browser-performance", "path": "performance.json", "media_type": "application/json"}
  ],
  "diagnostics": []
}
```

The exact schema belongs with ADR 009's event/result model and ADR 012's metrics model, but this ADR
fixes the boundary: external tools report structured data, not human text.

### Capability negotiation

Every adapter exposes a capability descriptor before execution:

```text
adapter name
adapter protocol version
adapter implementation version
tool name and version
language runtime and version
supported browser engines
supported browser channels
supported metrics
supported artifact kinds
supported capture policies
concurrency limit
required environment variables
```

Plan normalization validates browser scenarios against this descriptor. Unsupported metrics,
missing browsers, missing runtime packages, and incompatible protocol versions are setup failures.
They are not runtime surprises after the scheduler has started.

The initial metric vocabulary is intentionally small:

| Metric | Meaning |
|---|---|
| `browser.first_paint` | Performance Paint Timing `first-paint` start time in milliseconds |
| `browser.first_contentful_paint` | Performance Paint Timing `first-contentful-paint` start time in milliseconds |
| `browser.dom_content_loaded` | Navigation timing DOMContentLoaded completion in milliseconds |
| `browser.load` | Navigation timing load completion in milliseconds |
| `browser.operation_duration` | rampa monotonic duration for the adapter operation |

Browser metrics use the `browser.` namespace. They are not HTTP request metrics and must not be
merged into `http.duration`, `http.failed`, or server-side latency thresholds. Browser performance
entries are relative to the browser page's time origin; rampa stores them as durations in
milliseconds and records adapter operation duration separately using rampa's monotonic clock.

### Local server lifecycle

Starting a frontend development server is rampa lifecycle work, not adapter work. The Plan may name
a `command_server` with argv, cwd, environment overlay, readiness URL, startup timeout, shutdown
timeout, and captured stdout/stderr policy. rampa starts that server before browser attempts,
waits for readiness, and stops it during teardown.

The command is an argv vector, never an interpolated shell string. This follows the same defensive
shape as mature command execution systems: command construction, child-process I/O, exit
aggregation, and buffered diagnostics are explicit pieces rather than incidental shell behavior.

Adapters receive only a URL and run metadata. They do not decide how to build, serve, or mutate the
application under test.

### Artifact policy

Browser runs can produce large artifacts: traces, HAR files, screenshots, videos, console logs, and
performance JSON. They are run artifacts, not tracked repository files. The artifact model records:

- kind;
- media type;
- path or remote URI;
- scenario id;
- attempt id;
- adapter name and version;
- retention reason.

Capture policy starts with `off`, `on`, and `failure`. `failure` keeps the artifact only when the
attempt fails, times out, or is cancelled. This mirrors the useful pytest-playwright pattern:
intermediate files can be temporary, while retained files move under the run's artifact root after
the result is known.

Distributed mode later stores artifact references, not artifact bytes, in coordinator messages.
Large traces must not cross a metrics aggregation protocol by default.

### Timing and failure classification

Browser attempts preserve ADR 003's timing distinctions:

- scheduled start, assigned by the rampa scheduler;
- actual start, when adapter work begins;
- browser navigation start, from browser performance data when available;
- browser metric durations, from browser performance entries;
- adapter operation duration, from rampa monotonic time;
- completion, timeout, cancellation, or crash.

Navigation timeout, adapter timeout, server startup timeout, browser launch failure, page error,
unsupported metric, and adapter protocol failure are distinct failures. A timeout is not treated as
a generic non-zero exit. A command adapter crash keeps stderr/stdout diagnostics as artifacts and
returns an adapter failure classification.

### Relationship to Python profiling

Python command profiling and browser profiling share the same run/artifact surface, but they are
different profiling modes.

Python command profiling answers: where did a Python process spend CPU or wall time? Browser
profiling answers: when did a browser page reach user-visible milestones? A single `Plan` may
contain both, but their metric namespaces and integrity records stay separate.

### Testing requirements

The adapter layer is tested in three rings.

**Core contract tests** run in the default test suite with fake adapters. They validate capability
preflight, unsupported-feature rejection, timeout mapping, artifact retention, metric
normalization, stdout/stderr capture for command adapters, and no-import behavior when optional
dependencies are absent.

**Adapter compatibility tests** run for each installed adapter. The same behavioral tests exercise
the Python Playwright adapter and the command protocol adapter, using a local static page served by
rampa's own command-server lifecycle. These tests assert first-paint extraction, trace/HAR
retention, browser launch failure mapping, and cleanup after repeated attempts.

**Optional browser CI** installs browser binaries and runs the compatibility suite on a controlled
worker. The default Python-only job still passes without Playwright, Node, npm, or browser binaries.

## Consequences

### Positive

- rampa remains Python-first without making browser automation a required dependency.
- Playwright can work through Python bindings and through npm or other language runtimes without
  two public APIs.
- Adapter capability negotiation makes unsupported metrics and missing tools fail before the load
  schedule starts.
- Browser traces and HAR files become first-class artifacts while staying out of tracked files and
  metric aggregation messages.
- The same shape can later move to remote workers under ADR 013 without redesigning the authoring
  API.

### Tradeoffs

- A structured adapter protocol is more work than shelling out and parsing text.
- Browser metrics are less deterministic than command benchmarks and need optional CI separation.
- Supporting both Python and npm adapters creates versioning work: rampa must test protocol
  compatibility, not just Python imports.
- `adapter="auto"` is convenient but risky; normalization must record the selected adapter so
  results are explainable.

### Risks

- **Metric confusion.** Browser paint timings may be mistaken for server latency. Mitigation:
  browser metrics live under `browser.` and reports label the adapter and metric source.
- **Hidden fallback.** A missing Python package could silently switch to npm and change results.
  Mitigation: adapter selection is fixed during normalization and recorded.
- **Artifact bloat.** Traces and HAR files can grow quickly. Mitigation: retention policy, artifact
  roots, and remote references rather than coordinator payloads.
- **Protocol drift.** npm and Python adapters may diverge. Mitigation: shared adapter contract
  tests and protocol-version checks.
- **Toolchain security.** Running npm packages or arbitrary commands is powerful. Mitigation:
  argv-only command configuration, explicit cwd/env, no implicit shell, timeouts, and captured
  diagnostics.

## Relationship to other ADRs

- ADR 002 classifies independent browser tools behind message boundaries as worker-shaped
  boundaries.
- ADR 003 supplies timing and failure-classification rules.
- ADR 006 supplies profiling integrity and artifact expectations.
- ADR 008 supplies the `Plan`, `Scenario`, and behavior-reference boundary.
- ADR 009 defines the event/result records this adapter emits.
- ADR 011 defines the adapter contract this ADR specializes for browser work.
- ADR 012 defines exact metric names, units, merge rules, and threshold behavior.
- ADR 013 defines how browser adapters run remotely and how artifact references cross a
  distributed protocol.

## Prior art

- **Playwright** (Apache-2.0, `microsoft/playwright@v1.60.0`) separates public clients from server-side
  dispatchers through generated protocol validation, GUID-scoped object references, explicit
  disposal, and progress controllers for timeout/cancellation:
  [`packages/playwright-core/src/client/channelOwner.ts`](https://github.com/microsoft/playwright/blob/v1.60.0/packages/playwright-core/src/client/channelOwner.ts),
  [`packages/playwright-core/src/server/dispatchers/dispatcher.ts`](https://github.com/microsoft/playwright/blob/v1.60.0/packages/playwright-core/src/server/dispatchers/dispatcher.ts),
  [`packages/playwright-core/src/server/progress.ts`](https://github.com/microsoft/playwright/blob/v1.60.0/packages/playwright-core/src/server/progress.ts).
- **Playwright component testing** (Apache-2.0, `microsoft/playwright@v1.60.0`) keeps framework-specific React
  and Vue adapters thin around a shared Vite-backed core:
  [`packages/playwright-ct-core/src/vitePlugin.ts`](https://github.com/microsoft/playwright/blob/v1.60.0/packages/playwright-ct-core/src/vitePlugin.ts),
  [`packages/playwright-ct-react/index.js`](https://github.com/microsoft/playwright/blob/v1.60.0/packages/playwright-ct-react/index.js).
- **pytest-playwright** (Apache-2.0, `microsoft/playwright-pytest@v0.8.0`) shows a Python-facing adapter that
  translates pytest fixtures/options into Playwright browser/context/page lifecycles and keeps
  trace/video/screenshot artifacts according to retention policy:
  [`pytest_playwright.py`](https://github.com/microsoft/playwright-pytest/blob/v0.8.0/pytest-playwright/pytest_playwright/pytest_playwright.py).
- **Distributed Load Testing on AWS** (Apache-2.0, `aws-solutions/distributed-load-testing-on-aws@v4.1.0`)
  treats external load tools as containerized execution capabilities while the control plane stores
  scenarios, starts tasks, streams live data, and persists artifacts:
  [`source/cli/src/lib/scenario-launcher.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/cli/src/lib/scenario-launcher.ts),
  [`source/infrastructure/lib/back-end/step-functions.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/infrastructure/lib/back-end/step-functions.ts),
  [`source/task-runner/src/task-definition.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/task-runner/src/task-definition.ts).
- **SQLAlchemy dialect loading** (MIT, `sqlalchemy/sqlalchemy@rel_2_0_50`)
  demonstrates a small built-in registry with entry-point extension for third-party drivers:
  [`lib/sqlalchemy/util/langhelpers.py`](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/util/langhelpers.py),
  [`lib/sqlalchemy/dialects/__init__.py`](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/dialects/__init__.py).
- **fd command execution** (MIT/Apache-2.0, `sharkdp/fd@v10.4.2`) captures child-process stdout/stderr, flushes
  diagnostics on the first failing child, and aggregates child exits into one command result:
  [`src/exec/command.rs`](https://github.com/sharkdp/fd/blob/v10.4.2/src/exec/command.rs).

## Final position

Browser profiling is not a special case inside the core runner. It is a protocol-shaped adapter
capability. rampa owns the Python API, scheduling, failure model, metric namespace, and artifact
contract; adapters own the browser automation details for Python, npm, or another runtime and must
prove their results through the same adapter contract tests.
