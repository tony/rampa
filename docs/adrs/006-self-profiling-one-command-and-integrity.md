# ADR 006: Self-Profiling — One Command Away and Load-Test Integrity

Status: Proposed
Date: 2026-05-29

## Context

The engineering policy states that profiling must be one command away: a developer or agent
should be able to profile a test, profile normal runtime usage, record profiler output, and
inspect the result through documented commands without inventing a workflow. ADR 005 makes
regressions detectable; this ADR makes them investigable.

Profiling a load generator carries a constraint ordinary profiling does not. The tool's own
overhead competes with the latency it measures, so a profiler that distorts timing can turn a
diagnosis into a fiction. The questions a load-test profile must answer — is the generator
CPU-bound, is it starved on the GIL, is the cost in scheduling or in metric reduction — depend on
distinguishing wall time from CPU time from GIL-held time, at low or zero overhead.

## Decision

Profiling rampa is one documented command away, defaults to zero-runtime-dependency standard-library
tooling, and never distorts what a load test measures.

A developer can, with one command: profile a test, profile a normal run, and profile the native
accelerator; record the result in a standard, shareable format; and be shown how to inspect it.
The default tools add no runtime dependency. Profiling honors the measurement-integrity rules of
ADR 003.

## Scope

This ADR governs rampa's profiling workflow and tooling defaults: the one-command targets, the
default tools and output formats, the memory-growth check, and the integrity rules profiling must
observe. It does not cover regression detection (ADR 005) or the test harness (ADR 004).

## Requirements

### 1. One command, standard output, both paths

Documented `just`/script targets profile a test and profile a normal run, against both the
pure-Python and native paths, emit a standard format (`pstats`, collapsed stacks, speedscope, or
gecko), and print the command to inspect the result afterward. The developer never reconstructs
the workflow.

mypy's profiling script is the model: one command builds, runs `perf record`, and then prints the
exact command to analyze the captured profile
([`misc/profile_check.py`](https://github.com/python/mypy/blob/v1.20.2/misc/profile_check.py)).
orjson ships profiling as a literal one-liner
([`script/profile`](https://github.com/ijl/orjson/blob/3.11.9/script/profile)). ty exposes a
single `--profile`/`TY_PROFILE` flag that writes a flame profile, keeping spans available in a
release build so no debug redeploy is needed
([`crates/ty/src/logging.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ty/src/logging.rs)).

### 2. Standard library first

The default profilers add no runtime dependency. On rampa's supported Python 3.14 runtime, use
`cProfile`/`pstats` for deterministic call profiles
([`Lib/cProfile.py`](https://github.com/python/cpython/blob/v3.14.5/Lib/cProfile.py)). CPython's
stdlib sampling profiler, `python -m profiling.sampling`, is a Python 3.15+ option for attachable
wall, CPU, and GIL-mode sampling, including baseline-diff flamegraphs
([`Lib/profiling/sampling/`](https://github.com/python/cpython/tree/v3.15.0a1/Lib/profiling/sampling)).
Richer third-party tools (py-spy, austin, memray, scalene) are documented as options, never
required to install or run the package.

### 3. Memory-growth check

A memory check guards the paths a long-running generator stresses — connection pools, metric
buffers, sub-sinks. `pytest-memray`'s `@pytest.mark.limit_memory` is a ready-made check
([`bloomberg/pytest-memray`](https://github.com/bloomberg/pytest-memray/tree/v1.8.0),
[`bloomberg/memray`](https://github.com/bloomberg/memray/tree/v1.19.2)). This complements ADR 004's
repeat-and-diff leak check: one bounds peak allocation, the other proves the count flatlines.

### 4. Integrity (binds ADR 003)

Profiling must not change what a load test measures. Prefer low- or zero-overhead sampling, and
keep instrumentation zero-overhead when inactive — the principle behind CPython's PEP 669
`sys.monitoring`, which instruments bytecode in place and costs nothing when no tool is attached.
The wall-vs-CPU-vs-GIL distinction is documented for every profiling mode, because for an
I/O-bound generator a CPU profile and a wall profile answer different questions. Profile a
release-shaped build with symbols retained rather than a slow debug build.

### 5. The native path

Profiling the Rust accelerator is documented and does not require a debug redeploy: a profiling
build profile (maturin `--profile profiling`), `perf`/`flamegraph`/`samply`, and, where a build is
the target, a profile-guided-optimization loop. maturin implements the PGO instrument-train-rebuild
cycle ([`PyO3/maturin`](https://github.com/PyO3/maturin/tree/v1.13.3)); pydantic-core wires a
build-profiling target and a full PGO loop into its
[`Makefile`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/Makefile).

## Profiling record

A pull request that adds or changes a profiling workflow records:

```text
command:                 the documented just/script target
scope:                   a test | a normal run | the native accelerator
both paths:              python-only + native
tool:                    cProfile | profiling.sampling (Python 3.15+) | py-spy | austin | memray | scalene
overhead mode:           wall | cpu | gil
output format:           pstats | collapsed | speedscope | gecko | flamegraph
baseline diff:           none | diff-flamegraph vs named baseline
build:                   release-shaped, symbols kept (no debug redeploy)
integrity:               zero-overhead-when-off; does not alter measurement
```

## Pull request checklist

```text
[ ] Profiling a test and a run is one documented command, for both paths.
[ ] The default path uses standard-library tooling (no new runtime dependency).
[ ] A memory-growth check guards connection / buffer / metrics paths.
[ ] Profiling output is a standard, shareable format, and the inspect command is printed.
[ ] Profiling does not alter what the load test measures (wall/cpu/gil documented).
```

## Consequences

### Positive

- The "profiling one command away" policy becomes real tooling, not a sentence.
- Stdlib defaults keep the package dependency-free on Python 3.14, with attach, GIL-mode, and
  baseline-diff profiling available on Python 3.15+.
- The wall/CPU/GIL distinction lets a diagnosis of an I/O-bound generator be correct.
- A memory-growth check catches the leaks long runs expose before they ship.

### Tradeoffs

- The richest stdlib sampler (`profiling.sampling`) requires Python 3.15+; the supported Python
  3.14 runtime uses `cProfile` plus optional third-party tools.
- Maintaining one-command targets for both paths and the native build is ongoing upkeep.
- A memory-growth check adds a dependency to the dev/test extra (not the runtime).

### Risks

- Profiler distortion: a high-overhead profiler misattributes load-test cost. Mitigation: prefer
  sampling, document the overhead mode, profile release-shaped builds.
- Tool sprawl: requiring many profilers raises the barrier. Mitigation: stdlib default, the rest
  optional.

## Relationship to ADR 002, 003, 004, and 005

This ADR realizes the engineering policy's "profiling one command away" and binds it to ADR 003's
measurement-integrity rules. It investigates the regressions ADR 005 detects, profiles the harness
ADR 004 provides, and informs the per-path measurement ADR 002 requires before native code.

## Prior art

- **CPython** (`python/cpython`) — stdlib sampling profiler with attach, wall/CPU/GIL modes, and
  baseline-diff flamegraphs (`@v3.15.0a1`), deterministic `cProfile` (`@v3.14.5`), and PEP 669
  zero-overhead-when-off instrumentation:
  [`Lib/profiling/sampling/`](https://github.com/python/cpython/tree/v3.15.0a1/Lib/profiling/sampling),
  [`Lib/cProfile.py`](https://github.com/python/cpython/blob/v3.14.5/Lib/cProfile.py).
- **ty / ruff** (`astral-sh/ruff@0.15.14`) — one `--profile` flag → flame profile, spans kept in
  release builds:
  [`crates/ty/src/logging.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ty/src/logging.rs).
- **mypy** (`python/mypy@v1.20.2`) — one command profiles and prints the analysis command; runtime
  memory profiling:
  [`misc/profile_check.py`](https://github.com/python/mypy/blob/v1.20.2/misc/profile_check.py),
  [`mypy/memprofile.py`](https://github.com/python/mypy/blob/v1.20.2/mypy/memprofile.py).
- **orjson** (`ijl/orjson@3.11.9`) — profiling as a literal one-liner:
  [`script/profile`](https://github.com/ijl/orjson/blob/3.11.9/script/profile).
- **Profiler tools** — py-spy ([`benfred/py-spy@v0.4.2`](https://github.com/benfred/py-spy/tree/v0.4.2),
  attach + GIL mode + speedscope), austin
  ([`p403n1x87/austin@v4.0.0`](https://github.com/p403n1x87/austin/tree/v4.0.0), time + memory),
  memray ([`bloomberg/memray@v1.19.2`](https://github.com/bloomberg/memray/tree/v1.19.2)) with the
  `limit_memory` check ([`bloomberg/pytest-memray@v1.8.0`](https://github.com/bloomberg/pytest-memray/tree/v1.8.0)),
  and scalene ([`plasma-umass/scalene`](https://github.com/plasma-umass/scalene), no release tags;
  line-level CPU + memory).
- **maturin** (`PyO3/maturin@v1.13.3`) and **pydantic-core** (`pydantic/pydantic-core@v2.41.5`) —
  profiling build profile and a PGO instrument-train-rebuild loop:
  [`PyO3/maturin`](https://github.com/PyO3/maturin/tree/v1.13.3),
  [`pydantic-core/Makefile`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/Makefile).

## Final position

A regression you cannot profile in one command is a regression you will not investigate. rampa
keeps profiling one command away, dependency-free by default, and faithful to what a load test
measures — wall, CPU, or GIL, never distorted by the act of looking.
