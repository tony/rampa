# ADR 015: Project-Owned Benchmark Suites and Profile Adapters

Status: Proposed
Date: 2026-05-31

## Context

ADR 005 defines how rampa benchmarks itself, and ADR 006 defines how profiling stays one command
away. Those ADRs are necessary but too narrow for the surrounding Python projects: several projects
already have purpose-built benchmark and profiling workflows that live beside their own code,
fixtures, command-line entry points, and local data. rampa should not replace those workflows with a
central benchmark repository. It should give them a shared contract.

The project survey points to two strong existing shapes.

- agentgrep has a project-local benchmark harness with a committed TOML file, an ignored local
  overlay, cross-commit selectors, optional hyperfine timing, a Python fallback timer, structured
  JSON/NDJSON/Markdown/CSV outputs, and a test suite for the harness itself.
- rampa has purpose-built Python benchmark scripts with importable `run_benchmark(...)` functions
  and JSON-shaped results for throughput, scheduler precision, metric ingestion, and local HTTP
  overhead.

The other projects show why the contract must stay flexible.

- gp-sphinx records cProfile-backed evidence for selected pytest slices and uses the profile to
  distinguish genuine Sphinx builder cost from avoidable runner overhead.
- vcspull records duration fields, subprocess timeouts, and structured JSON/NDJSON output around
  command-heavy repository operations.
- libtmux and libtmux-mcp wrap external tmux subprocesses where stdout, stderr, exit status,
  timeout, and event-loop blocking are part of correctness.
- tmuxp made test performance deterministic by pinning the test shell environment, which is a
  reminder that benchmark suites need explicit environment controls.

The notes atlas adds the structural direction. SQLAlchemy's `PluginLoader` pattern gives built-ins
plus entry-point extensions plus runtime registration. setuptools' command lifecycle separates
option initialization, option injection, validation, and side effects. fd's command execution model
uses argv construction, buffered output, and explicit exit aggregation rather than incidental shell
behavior. hyperfine separates setup, warmup, measurement, cleanup, adaptive run counts, and raw
sample retention. pytest-playwright keeps artifact retention policy separate from temporary capture.
Distributed Load Testing on AWS keeps orchestration, workers, artifacts, and history separate from
the worker execution payload. Runtime profilers and trace channels make diagnostics observable
without making diagnostics define runtime behavior.

The design question is therefore: how can each project keep its own suite, while rampa provides the
same small contract, adapter model, result model, profiling workflow, and future distributed shape?

## Decision

rampa will support project-owned benchmark suites through a `rampa.bench` surface. A suite belongs
to the project being measured. rampa loads, validates, executes, profiles, compares, and normalizes
that suite, but it does not centralize the benchmark definitions or take ownership of the measured
project's fixtures.

The contract has four layers:

1. a project-owned suite manifest or Python suite object;
2. adapters that know how to run one benchmark target;
3. measurement and profiling engines that wrap adapter attempts;
4. a normalized result model that can be compared locally today and shipped to workers later.

The simple path is one command against a manifest. The advanced path adds adapters, local overlays,
workspace selection, artifact retention, and eventually remote execution without changing the
project-owned suite contract.

## Scope

This ADR governs benchmark-suite ownership, the manifest shape, adapter families, profiling
integration, result normalization, baselines, cross-repository execution, and the future distributed
boundary for benchmark suites. It does not replace ADR 005's self-benchmarking policy, ADR 006's
profiling integrity rules, ADR 008's load-test `Plan`, or ADR 014's browser adapter contract. It
extends the same architectural rules to benchmark suites that live outside rampa itself.

## Public API

The Python surface is the primary API. The CLI and manifest format are conveniences over the same
objects.

The shortest path runs a project-owned manifest directly:

```python
import rampa

result = rampa.bench.run(
    "benchmarks/rampa.toml",
    select="search-limit-50",
    baseline="trunk",
    profile="search-cprofile",
)
```

The CLI is the same loader and runner:

```console
$ rampa bench run benchmarks/rampa.toml --select search-limit-50 --profile search-cprofile
```

That path is the default example. The builder API exists when a project wants to assemble or extend
a suite from Python code.

```python
import rampa

suite = rampa.bench.suite("agentgrep")
suite.command(
    "search-limit-50",
    argv=[
        "uv",
        "run",
        "agentgrep",
        "search",
        "--no-progress",
        "--limit",
        "50",
        "{query}",
    ],
    params={"query": "tmux"},
)

result = rampa.bench.run(
    suite,
    baseline=rampa.bench.baseline("trunk"),
    profile=rampa.bench.profile("cprofile"),
)
```

A project can keep the same suite in a manifest:

```toml
version = 1
name = "agentgrep"

[defaults]
runs = 3
warmup = 1
timeout = "5m"
artifact_root = ".rampa-artifacts"

[[bench]]
name = "search-limit-50"
adapter = "command"
argv = [
  "uv",
  "run",
  "agentgrep",
  "search",
  "--no-progress",
  "--limit",
  "50",
  "{query}",
]

[bench.params]
query = "tmux"

[[profile]]
name = "search-cprofile"
target = "search-limit-50"
tool = "cprofile"
format = "pstats"
capture = "on"
```

The manifest is not the only authoring form. Purpose-built Python benchmark scripts can expose a
callable and register it from Python:

```python
suite.python(
    "scheduler-precision",
    callable="scripts.bench_scheduler:run_benchmark",
    params={"rate": 1000.0, "duration": 2.0, "max_vus": 100},
)
```

That keeps rampa's current importable benchmark functions first-class instead of forcing them
through subprocesses.

## Suite Ownership and Layering

Each measured project owns its suite files. rampa may discover common filenames such as
`benchmarks/rampa.toml`, `.rampa/bench.toml`, or `scripts/benchmark.toml`, but discovery is only a
convenience. The user can always pass an explicit path or Python suite object.

Configuration layers use the existing successful pattern:

1. built-in defaults from rampa's schema;
2. the committed project suite manifest;
3. an ignored local overlay for machine-specific commands, run counts, browser channels, or data
   paths;
4. CLI or Python-call overrides.

The merged suite is validated before any side effects. Unknown keys fail loudly. A dry-run command
prints the normalized suite, selected adapters, resolved argv vectors, environment overlays, and
artifact roots without executing attempts.

Local overlays are not silently used for remote execution. A remote run records the resolved suite
input explicitly so a worker can reproduce what the coordinator meant to run.

## Adapter Registry

rampa uses a registry with three lookup paths, following the SQLAlchemy loader shape:

- built-in adapters for command, Python callable, pytest, browser, and external command protocol;
- package entry points for third-party adapters;
- runtime registration for tests and embedding.

Every adapter declares capabilities before a suite starts:

```text
adapter name
adapter version
protocol version
supported target kinds
supported measurement engines
supported profiling engines
supported artifact kinds
concurrency limit
required tools and environment variables
remote-execution support
```

Suite normalization checks benchmark targets against those capabilities. Missing executables,
missing Python imports, unsupported profile tools, unsupported browser metrics, and incompatible
adapter protocols are setup failures, not surprises after timing begins.

## Adapter Families

The initial adapters cover the local project patterns without inventing a new benchmark DSL.

**Command adapter.** Runs an argv vector with explicit cwd, environment overlay, stdin policy,
stdout/stderr capture policy, timeout, and expected exit behavior. It never requires an interpolated
shell string. A compatibility importer may read existing string commands from project harnesses, but
the normalized form is argv.

**Python callable adapter.** Imports a callable by object or import path, passes typed parameters,
and accepts either a normalized rampa result or a JSON-like mapping. This is the natural adapter for
purpose-built benchmark scripts that already expose `run_benchmark(...)` functions.

**Pytest adapter.** Runs a test selection under a controlled pytest subprocess or in an isolated
pytester-style project when the plugin-under-test must not pollute the outer process. It can collect
durations, counts, artifacts, and profiler output while preserving pytest's own exit semantics.

**Browser adapter.** Uses ADR 014. Browser first-paint probes and Playwright-backed traces are just
benchmark targets whose metrics live under the `browser.` namespace.

**External command protocol adapter.** Runs an installed tool, npm package, or other language
runtime over a versioned JSON stdio protocol. It is the long-tail escape hatch for tools that should
not become Python dependencies.

Adapters own execution mechanics. Measurement engines own timing, profiling, repeats, warmups, and
comparison. Keeping those responsibilities separate prevents a command adapter, browser adapter, or
pytest adapter from each inventing its own incompatible run semantics.

## Measurement and Profiling Engines

A benchmark target can be measured by one or more engines:

- built-in wall-clock timing with monotonic clocks;
- hyperfine, when installed, for command-shaped wall-clock timing with warmup and raw samples;
- deterministic count engines from ADR 005, for call counts, allocation counts, or domain counts;
- cProfile from ADR 006, as the default zero-dependency Python call profiler;
- optional profilers such as py-spy, memray, `perf`, or language-specific profilers;
- browser performance engines from ADR 014.

Profiles are run artifacts by default, not authoritative load-test results. A profile may support a
performance claim only when the selected mode, expected overhead, and named baseline are recorded,
as required by ADR 006. High-overhead deterministic profiling such as cProfile is useful for call
shape diagnosis but does not produce trustworthy latency numbers.

Profiling applies to tests, commands, normal project entry points, browser attempts, and Python
callables through the same result and artifact model:

```console
$ rampa bench profile benchmarks/rampa.toml --select scheduler-precision --tool cprofile
```

The command prints the inspect command for the generated artifact.

## Result Model

Every run produces a normalized suite result. The result keeps enough detail for local diagnosis and
enough structure for future distributed merging:

```text
suite id
project identity
suite manifest version
selected benchmark ids
selected adapter ids and versions
selected measurement and profiling engines
environment fingerprint
baseline name
attempt records
metric observations
mergeable summaries
artifacts
diagnostics
threshold or comparison verdicts
```

An attempt record carries:

```text
benchmark id
adapter id
attempt index
parameter values
scheduled start when applicable
actual start
end
status
exit code or failure classification
stdout and stderr references or excerpts
raw timing samples when available
metric observations
artifact references
diagnostics
```

The default benchmark metric namespace is separate from load-test protocol metrics:

| Metric | Meaning |
|---|---|
| `bench.wall_time` | Attempt wall duration measured by the selected timing engine |
| `bench.cpu_time` | CPU duration when the engine can report it |
| `bench.exit_code` | Process exit status for command-shaped targets |
| `bench.memory_peak` | Peak memory when measured |
| `bench.call_count` | Deterministic function-call count when measured |

Adapters may emit project-specific metrics, but units and aggregation rules must be declared. Raw
samples are preserved for local analysis when practical. Distributed summaries are mergeable; the
coordinator computes percentiles after merge and never averages worker percentiles.

## Baselines and Comparisons

Baselines are project-local unless explicitly exported to a shared result store. A baseline key
includes:

```text
suite id
benchmark id
metric name and unit
adapter id and version
measurement engine
Python version or runtime version
operating system family
implementation path when relevant
baseline name
schema version
```

Baseline names follow ADR 005: active development compares to a named development baseline, while
release-facing claims compare to tags or releases. Schema-breaking result changes require a major
schema version. Added fields or non-breaking metric additions require a minor schema version.

High-level JSON summaries and reviewed baselines may be tracked in the measured project when they
are part of the supported evidence surface. Large profiles, browser traces, HAR files, heap dumps,
and raw deep-dive artifacts stay out of tracked files.

## Artifact Policy

Artifacts use a common retention model:

- `off` stores no artifact;
- `on` retains the artifact for every attempt;
- `failure` retains the artifact only for failed, timed-out, or cancelled attempts.

Temporary capture and final retention are separate. An adapter may write to a temporary directory
during execution, but rampa moves or records retained artifacts only after the attempt outcome is
known. Artifact records include kind, media type, path or remote URI, benchmark id, attempt id,
adapter id, retention reason, and whether the content is safe to display inline.

The command adapter stores stdout and stderr as bounded diagnostics by default, with full streams as
artifacts only when requested or on failure. This follows fd's lesson: child-process output policy
must be explicit when concurrency enters the picture.

## Workspace and Cross-Codebase Execution

A workspace runner can enumerate multiple project-owned suites and run them through one command:

```console
$ rampa bench workspace run --suite benchmarks/rampa.toml --select agentgrep:search-limit-50
```

The workspace runner is an orchestrator, not a new suite owner. Each project keeps its own suite,
environment sync command, lockfile expectations, ignored local overlay, fixtures, and artifact
policy. rampa records those inputs in the normalized result so cross-codebase reports remain
explainable.

The runner isolates projects by cwd, environment, and setup command. It does not reuse one global
Python environment across unrelated projects. It can run independent projects concurrently up to
adapter-declared limits, but stdout/stderr capture, artifact roots, and exit aggregation remain
per project and per benchmark.

## Future Distributed Shape

The distributed form follows the control/data/read split recorded for ADR 013:

- the coordinator loads and validates the suite, resolves overlays, selects adapters, and creates a
  normalized benchmark plan;
- workers receive a code bundle or repository reference, environment spec, selected suite slice,
  adapter requirements, and artifact root;
- workers execute narrow benchmark attempts and return summaries plus artifact references;
- the read model stores status, history, diagnostics, and artifact links off the measurement path.

What crosses the worker boundary by default is a bounded summary, not raw profiles or full child
process output. Raw artifacts go to an artifact store and are referenced by URI. This preserves the
same rule as distributed load testing: ship summaries, merge summaries, then compute aggregates.

Remote execution is mostly packaging and lifecycle: same code, pinned environment, readiness,
start, stop, cleanup, artifact upload, and failure reporting. A benchmark suite that cannot state
those requirements locally is not ready to run remotely.

## Testing Requirements

rampa tests this system in layers:

- schema tests for manifests, local overlays, dry-run normalization, and unknown-key failures;
- fake-adapter tests for capability negotiation, timeout mapping, artifact retention, diagnostics,
  and result normalization;
- command-adapter black-box tests that assert argv handling, stdout/stderr policy, missing
  executable classification, non-zero exit aggregation, and timeout behavior;
- Python-callable tests that import and run benchmark functions without a subprocess;
- pytest-adapter tests that use subprocess isolation where plugin loading matters;
- browser-adapter compatibility tests from ADR 014;
- workspace tests with two tiny project fixtures to prove per-project isolation.

Optional adapter packages run their own compatibility suites. The default rampa test suite must pass
without hyperfine, Playwright, Node, npm, browser binaries, py-spy, or memray installed.

## Consequences

### Positive

- Each project keeps its benchmarks next to the code, data, and fixtures they measure.
- rampa provides one result, artifact, baseline, and adapter contract across commands, Python
  callables, pytest slices, browser probes, and external runtimes.
- The simple path stays small: one manifest and one command.
- Existing bespoke harnesses can be imported incrementally instead of rewritten.
- The same normalized suite can later move to remote workers without a second API.

### Tradeoffs

- A manifest schema, adapter registry, and result model are more work than a single benchmark
  script.
- Supporting command strings as an import compatibility shape creates migration work toward argv
  vectors.
- Cross-codebase execution needs careful environment isolation to avoid producing incomparable
  results.
- Optional profiler and browser tools require compatibility tests but cannot be mandatory runtime
  dependencies.

### Risks

- **Over-centralization.** rampa could become a central benchmark repository. Mitigation: suites are
  project-owned; rampa owns only the contract and runner.
- **Metric confusion.** Browser, command, Python, and load-test metrics can be mistaken for each
  other. Mitigation: explicit namespaces, units, and adapter metadata.
- **Shell drift.** String commands and inherited environment state produce non-reproducible runs.
  Mitigation: normalize to argv, declare cwd/env, and record the environment fingerprint.
- **Artifact bloat.** Profiles and traces can grow quickly. Mitigation: retention policy and
  artifact references rather than tracked files or coordinator payloads.
- **False distribution confidence.** A local suite with hidden setup assumptions will fail remotely.
  Mitigation: remote execution requires explicit environment and bundle inputs.

## Relationship to Other ADRs

- ADR 005 supplies baseline naming, deterministic count checks, and latency measurement discipline.
- ADR 006 supplies profiling integrity, default profiler choices, and artifact expectations.
- ADR 008 supplies the normalized-plan mindset that this ADR mirrors for benchmark suites.
- ADR 009 supplies the operation attempt and artifact records used for benchmark attempts.
- ADR 010 supplies repeat, warmup, timeout, and scheduled-versus-actual timing semantics.
- ADR 011 supplies the adapter contract for command, Python callable, pytest, browser, and external
  protocol targets.
- ADR 012 supplies metric names, mergeable summaries, rates, percentiles, and thresholds.
- ADR 013 defines the remote execution driver, code bundle, environment spec, start barrier,
  artifact store, and read model used when suite runs leave the local machine.
- ADR 014 supplies the browser adapter family used by frontend first-paint profiling.

## Prior Art

- **agentgrep project harness** — project-owned TOML, local overlay, cross-commit selectors,
  hyperfine plus Python fallback, raw samples, and tested renderers.
- **rampa benchmark scripts** — purpose-built Python callables with JSON-shaped results for engine,
  scheduler, metric, and HTTP overhead paths.
- **gp-sphinx profiling notes** — cProfile evidence tied to selected pytest slices and a human
  explanation of where time is spent.
- **vcspull, libtmux, libtmux-mcp, and tmuxp** — command-heavy Python projects where subprocess
  output, timeout, environment, and diagnostics are part of the measured behavior.
- **SQLAlchemy** (MIT, `sqlalchemy/sqlalchemy@rel_2_0_50`) — built-in registry, entry-point
  discovery, and runtime registration through one loader pattern:
  [`lib/sqlalchemy/util/langhelpers.py`](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/util/langhelpers.py),
  [`lib/sqlalchemy/dialects/__init__.py`](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/dialects/__init__.py).
- **setuptools** (MIT, `pypa/setuptools@v80.9.0`) — command lifecycle that validates options
  before side effects:
  [`setuptools/dist.py`](https://github.com/pypa/setuptools/blob/v80.9.0/setuptools/dist.py),
  [`setuptools/command/build.py`](https://github.com/pypa/setuptools/blob/v80.9.0/setuptools/command/build.py),
  [`setuptools/command/dist_info.py`](https://github.com/pypa/setuptools/blob/v80.9.0/setuptools/command/dist_info.py).
- **fd** (MIT/Apache-2.0, `sharkdp/fd@v10.4.2`) — argv-shaped command execution, output
  buffering, and explicit exit aggregation:
  [`src/exec/command.rs`](https://github.com/sharkdp/fd/blob/v10.4.2/src/exec/command.rs).
- **hyperfine** (MIT/Apache-2.0, `sharkdp/hyperfine@v1.20.0`) — setup, warmup, adaptive run
  counts, cleanup, raw sample retention, and export formats:
  [`src/benchmark/executor.rs`](https://github.com/sharkdp/hyperfine/blob/v1.20.0/src/benchmark/executor.rs),
  [`src/options.rs`](https://github.com/sharkdp/hyperfine/blob/v1.20.0/src/options.rs),
  [`src/export/json.rs`](https://github.com/sharkdp/hyperfine/blob/v1.20.0/src/export/json.rs).
- **pytest-playwright** (Apache-2.0, `microsoft/playwright-pytest@v0.8.0`) — artifact retention
  policy and subprocess-backed black-box tests:
  [`pytest_playwright.py`](https://github.com/microsoft/playwright-pytest/blob/v0.8.0/pytest-playwright/pytest_playwright/pytest_playwright.py).
- **Distributed Load Testing on AWS** (Apache-2.0,
  `aws-solutions/distributed-load-testing-on-aws@v4.1.0`) — orchestration, workers, artifacts,
  and read-model separation:
  [`source/infrastructure/lib/back-end/step-functions.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/infrastructure/lib/back-end/step-functions.ts),
  [`source/task-runner/src/task-definition.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/task-runner/src/task-definition.ts),
  [`source/mcp-server/src/tools/get-test-run-artifacts.ts`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/mcp-server/src/tools/get-test-run-artifacts.ts).

## Final Position

rampa should make benchmark and profiling suites portable without flattening their project-specific
fixtures and workflows. The measured project owns the suite. rampa owns the contract: adapters,
profiling engines, artifacts, baselines, result normalization, and eventually distribution.
