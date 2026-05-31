# ADR 005: Self-Benchmarking — Baselines and Regression Detection

Status: Proposed
Date: 2026-05-29

## Context

ADR 002 forbids native code until a measurement of the user-visible path, against a named
baseline, proves a limit Python cannot resolve. ADR 003 requires native load-generation work to
benchmark the user-visible path — scheduling, metrics, reporting — not a function in isolation.
The engineering policy already says performance claims must name a comparison baseline (trunk,
tag, or release). None of that is enforceable unless rampa maintains a standing benchmark, a
named baseline, and a way to notice when performance changes.

A load generator has a constraint most projects do not: **wall-clock latency is simultaneously
the product it sells and a quantity too noisy to decide a pull request on.** A benchmark that
fails a pull request because a shared runner was busy trains everyone to ignore it. Yet the
per-request path is exactly where a silent regression would hide.

The resolution, drawn from how mature projects manage performance, is to keep two activities
separate: **notice regressions deterministically without wall-clock, and measure latency and
throughput against a named baseline, deliberately, away from the pull-request path.**

## Decision

rampa separates two activities and does not conflate them.

- **Deterministic regression detection** runs on every pull request. It asserts *counts* —
  domain events, connections, and carefully scoped function calls or allocations — against a
  checked-in baseline. Because it never reads wall-clock time, it never flakes, so it can block a
  merge honestly.
- **Latency and throughput measurement** runs deliberately — on a label or a schedule, on a
  controlled machine — not on every pull request. It compares against a named baseline and reports
  a geometric mean.

No native code is justified without a latency-or-throughput measurement of the user-visible path
against a named baseline. This is the concrete form of ADR 002's default rule and ADR 003's
benchmark policy.

## Scope

This ADR governs how rampa benchmarks itself and notices performance regressions: the
count-based regression checks, the latency/throughput measurement discipline, baseline naming and
storage, and benchmark hygiene. It does not cover one-off profiling (ADR 006) or the test harness
the benchmarks run on (ADR 004).

## Requirements

### 1. Deterministic regression detection (every pull request)

The hot paths — request scheduling, per-sample metric ingestion, metric reduction — have
assertions on **counts, not time**. The first gates are domain counters: scheduled slots,
operation attempts, emitted metric observations, summary merges, connection opens, and connection
reuses. Function-call and allocation counts are still useful, but only for isolated, stable hot
paths where interpreter noise, tool overhead, and acceptable variance are understood and reviewed.
The baseline is **checked into the repository and keyed by both environment and implementation
path** (whether the accelerator is present), so the pure-Python and native paths are checked
separately, per ADR 001. A regenerate flag rewrites the baseline deliberately; the check fails when
a count drifts beyond a documented tolerance.

SQLAlchemy is the reference: `@profiling.function_call_count(variance=0.10)` runs a function
under `cProfile`, reads `total_calls`, and fails on drift from a per-environment baseline checked
into the tree — its `git log` on that file is the performance history.
See [`lib/sqlalchemy/testing/profiling.py`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/testing/profiling.py),
the checked-in baseline [`test/profiles.txt`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/test/profiles.txt),
and [`test/aaa_profiling/`](https://github.com/zzzeek/sqlalchemy/tree/rel_2_0_50/test/aaa_profiling).
Django uses the same philosophy for round-trips with `assertNumQueries`
([`django/test/testcases.py`](https://github.com/django/django/blob/5.2.8/django/test/testcases.py)) —
the analog of rampa's ADR 003 connection accounting.

### 2. Latency and throughput measurement (named baseline, run deliberately)

Latency and throughput are measured against a **named baseline**: trunk or the merge-base for
active development, a tag or release for release-facing claims. Results report a geometric mean
with reproducibility controls (seeded randomness, pinned upstream state, a fixed machine). For
micro-paths, prefer a deterministic measure such as instruction counts (cachegrind-style) over
wall-clock; reserve wall-clock for a controlled machine. Include an **end-to-end throughput
measurement** — rampa driving a local target — for the generator's own ceiling. This runs on a
label or a schedule, never on every pull request.

CodSpeed is the de-facto standard for hybrid Python/Rust projects: instruction-count measurement
that is deterministic in CI, comparing each pull request against its base. ruff keeps one bench
source runnable both locally and under CodSpeed behind a `#[cfg(codspeed)]` shim and a merge-base
diff ([`crates/ruff_benchmark/src/criterion.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ruff_benchmark/src/criterion.rs),
[`.github/workflows/ci.yaml`](https://github.com/astral-sh/ruff/blob/0.15.14/.github/workflows/ci.yaml)),
and uses a wall-time benchmark against real projects for the load-shaped case
([`crates/ruff_benchmark/benches/ty_walltime.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ruff_benchmark/benches/ty_walltime.rs)).
pydantic-core and pydantic run `pytest-codspeed` on the Python surface against a profiling-built
wheel ([`pydantic-core/.github/workflows/codspeed.yml`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/.github/workflows/codspeed.yml),
[`pydantic/tests/benchmarks/test_model_validation.py`](https://github.com/pydantic/pydantic/blob/v2.10.6/tests/benchmarks/test_model_validation.py)).
The end-to-end shape is axum's: stand up a real server and point a separate load generator
(`rewrk`) at it ([`axum/benches/benches.rs`](https://github.com/tokio-rs/axum/blob/axum-v0.8.9/axum/benches/benches.rs),
[`lnx-search/rewrk`](https://github.com/lnx-search/rewrk/tree/0.3.2)).

### 3. Reproducibility and baseline naming

A claim names its baseline; an unnamed comparison is not a result. Determinism comes from seeded
randomness, pinned upstream state, and a controlled machine. uv pins its benchmark inputs by
priming a real cache and freezing the index with `--exclude-newer`
([`.github/workflows/bench.yml`](https://github.com/astral-sh/uv/blob/0.11.16/.github/workflows/bench.yml),
[`BENCHMARKS.md`](https://github.com/astral-sh/uv/blob/0.11.16/BENCHMARKS.md)); mypy compares
commits by cloning each, building in parallel, and averaging N runs with a fixed `PYTHONHASHSEED`
([`misc/perf_compare.py`](https://github.com/python/mypy/blob/v1.20.2/misc/perf_compare.py)).
CPython states perf claims as a geometric mean over a named suite (`pyperf`/`pyperformance`),
and ships a single-thread-vs-N-thread scaling benchmark with CPU-affinity pinning
([`Tools/ftscalingbench/ftscalingbench.py`](https://github.com/python/cpython/blob/v3.14.5/Tools/ftscalingbench/ftscalingbench.py),
[`Tools/scripts/sortperf.py`](https://github.com/python/cpython/blob/v3.14.5/Tools/scripts/sortperf.py)).

### 4. Hygiene and storage

Benchmarks are disabled by default in the normal test run and runnable with one command; they
emit structured JSON for tracking; large traces, dumps, and profiler captures stay out of tracked
files (per the engineering policy). pydantic disables benchmarks by default and exposes a single
`make benchmark` ([`Makefile`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/Makefile)).
Expensive or hardware-sensitive latency runs may live in a sibling repository or behind a label,
as Django keeps its ASV suite in an external repo triggered by a `benchmark` label
([`docs/internals/contributing/writing-code/submitting-patches.txt`](https://github.com/django/django/blob/5.2.8/docs/internals/contributing/writing-code/submitting-patches.txt),
[`django/django-asv`](https://github.com/django/django-asv)) and polars runs its heavy benchmarks
on a self-hosted machine against an external dataset
([`.github/workflows/benchmark-remote.yml`](https://github.com/pola-rs/polars/blob/rs-0.53.0/.github/workflows/benchmark-remote.yml)).

## Benchmark record

A pull request that adds or changes a benchmark, or that justifies native code, records:

```text
kind:                    deterministic regression detection (counts) | latency | throughput
metric:                  scheduled-slot-count | operation-attempt-count |
                         metric-observation-count | summary-merge-count |
                         event/connection-count | call-count | allocation-count |
                         instruction-count | wall-time
baseline:                trunk | merge-base | tag | release (named)
both paths:              python-only + native, keyed separately
tolerance:               documented drift allowed before the count check fails
reproducibility:         seeded RNG | pinned upstream | fixed machine | geometric mean
runs:                    every pull request | on a label | on a schedule
storage:                 checked-in baseline file | CI service | sibling repo
artifacts:               JSON results; large traces kept out of the tree
```

## Pull request checklist

```text
[ ] Native code (if any) is justified by a latency-or-throughput measurement of the user-visible path vs a named baseline.
[ ] Hot-path changes have deterministic domain-count assertions; function-call or allocation
    counters are scoped to stable hot paths with reviewed tolerances.
[ ] The count baseline is checked in and keyed by environment and by whether the accelerator is present.
[ ] Latency / throughput runs name their baseline and report a geometric mean with reproducibility controls.
[ ] Benchmarks are disabled by default and runnable in one command.
[ ] Large traces / dumps are kept out of tracked files.
```

## Consequences

### Positive

- ADR 002's "prove the bottleneck against a named baseline" becomes a concrete requirement, not a
  hope.
- The count assertions notice per-request regressions deterministically, immune to CI timing
  noise.
- Both implementation paths are checked separately, so native/Python drift surfaces immediately.
- Latency claims always carry a named baseline.

### Tradeoffs

- Two separate activities are more machinery than a single `pytest-benchmark` run.
- A checked-in count baseline must be regenerated deliberately and reviewed when it changes.
- A controlled machine (or a CI service) is required for trustworthy latency numbers.

### Risks

- A tolerance set too wide makes the count assertions meaningless. Mitigation: document and review
  the tolerance.
- Wall-clock creeping into the per-pull-request checks re-introduces flakiness. Mitigation: the
  per-pull-request checks assert counts only.
- Stale baselines block legitimate change. Mitigation: a reviewed regenerate flow.

## Relationship to ADR 001, 002, 003, and 004

This ADR makes ADR 002's default rule and ADR 003's benchmark policy enforceable, and it checks
both ADR 001 paths separately. It runs on the harness defined in ADR 004. ADR 006 covers the
profiling used to investigate a regression these checks detect.

## Prior art

- **SQLAlchemy** (`zzzeek/sqlalchemy@rel_2_0_50`) — deterministic function-call-count checks with
  a checked-in, per-environment baseline:
  [`lib/sqlalchemy/testing/profiling.py`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/testing/profiling.py),
  [`test/profiles.txt`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/test/profiles.txt),
  [`test/aaa_profiling/`](https://github.com/zzzeek/sqlalchemy/tree/rel_2_0_50/test/aaa_profiling).
- **Django** (`django/django@5.2.8`) — `assertNumQueries` round-trip check; ASV suite kept in an
  external repo behind a `benchmark` label:
  [`django/test/testcases.py`](https://github.com/django/django/blob/5.2.8/django/test/testcases.py),
  [`docs/internals/contributing/writing-code/submitting-patches.txt`](https://github.com/django/django/blob/5.2.8/docs/internals/contributing/writing-code/submitting-patches.txt),
  [`django/django-asv`](https://github.com/django/django-asv) (no release tags).
- **ruff** (`astral-sh/ruff@0.15.14`) — one bench source, two backends via `#[cfg(codspeed)]`;
  merge-base diff; wall-time benchmark on real projects:
  [`crates/ruff_benchmark/src/criterion.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ruff_benchmark/src/criterion.rs),
  [`.github/workflows/ci.yaml`](https://github.com/astral-sh/ruff/blob/0.15.14/.github/workflows/ci.yaml),
  [`crates/ruff_benchmark/benches/ty_walltime.rs`](https://github.com/astral-sh/ruff/blob/0.15.14/crates/ruff_benchmark/benches/ty_walltime.rs).
- **uv** (`astral-sh/uv@0.11.16`) — pinned-input determinism, competitor harness:
  [`.github/workflows/bench.yml`](https://github.com/astral-sh/uv/blob/0.11.16/.github/workflows/bench.yml),
  [`crates/uv-bench/Cargo.toml`](https://github.com/astral-sh/uv/blob/0.11.16/crates/uv-bench/Cargo.toml),
  [`BENCHMARKS.md`](https://github.com/astral-sh/uv/blob/0.11.16/BENCHMARKS.md),
  [`scripts/benchmark/`](https://github.com/astral-sh/uv/tree/0.11.16/scripts/benchmark).
- **pydantic-core** (`pydantic/pydantic-core@v2.41.5`) and **pydantic** (`pydantic/pydantic@v2.10.6`) —
  `pytest-codspeed` against a profiling-built wheel; one-command, disabled-by-default benchmarks:
  [`pydantic-core/.github/workflows/codspeed.yml`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/.github/workflows/codspeed.yml),
  [`pydantic-core/Makefile`](https://github.com/pydantic/pydantic-core/blob/v2.41.5/Makefile),
  [`pydantic/.github/workflows/codspeed.yml`](https://github.com/pydantic/pydantic/blob/v2.10.6/.github/workflows/codspeed.yml),
  [`pydantic/tests/benchmarks/test_model_validation.py`](https://github.com/pydantic/pydantic/blob/v2.10.6/tests/benchmarks/test_model_validation.py).
- **pyo3** (`PyO3/pyo3@v0.28.3`) — one `nox` session driving both Rust and Python benchmarks under
  CodSpeed:
  [`.github/workflows/benches.yml`](https://github.com/PyO3/pyo3/blob/v0.28.3/.github/workflows/benches.yml),
  [`noxfile.py`](https://github.com/PyO3/pyo3/blob/v0.28.3/noxfile.py).
  CodSpeed action: [`CodSpeedHQ/action`](https://github.com/CodSpeedHQ/action/tree/v4.17.0).
- **CPython** (`python/cpython@v3.14.5`) — geometric-mean claims over a named suite; scaling
  benchmark with CPU pinning:
  [`Tools/ftscalingbench/ftscalingbench.py`](https://github.com/python/cpython/blob/v3.14.5/Tools/ftscalingbench/ftscalingbench.py),
  [`Tools/scripts/sortperf.py`](https://github.com/python/cpython/blob/v3.14.5/Tools/scripts/sortperf.py).
  Runners: [`psf/pyperf`](https://github.com/psf/pyperf/tree/2.10.0),
  [`python/pyperformance`](https://github.com/python/pyperformance/tree/1.14.0).
- **mypy** (`python/mypy@v1.20.2`) — clone-per-commit, parallel build, N-runs-averaged comparison:
  [`misc/perf_compare.py`](https://github.com/python/mypy/blob/v1.20.2/misc/perf_compare.py).
- **polars** (`pola-rs/polars@rs-0.53.0`) — self-hosted heavy benchmark; parametric property
  fuzzing for parity:
  [`.github/workflows/benchmark-remote.yml`](https://github.com/pola-rs/polars/blob/rs-0.53.0/.github/workflows/benchmark-remote.yml),
  [`py-polars/src/polars/testing/parametric/`](https://github.com/pola-rs/polars/tree/rs-0.53.0/py-polars/src/polars/testing/parametric).
- **axum** (`tokio-rs/axum@axum-v0.8.9`) and **rewrk** (`lnx-search/rewrk@0.3.2`) — end-to-end:
  serve a real router, drive it with a separate load generator:
  [`axum/benches/benches.rs`](https://github.com/tokio-rs/axum/blob/axum-v0.8.9/axum/benches/benches.rs),
  [`lnx-search/rewrk`](https://github.com/lnx-search/rewrk/tree/0.3.2).
- **orjson** (`ijl/orjson@3.11.9`) — autosave + correctness-asserting benchmarks, no SaaS:
  [`script/pybench`](https://github.com/ijl/orjson/blob/3.11.9/script/pybench),
  [`bench/data.py`](https://github.com/ijl/orjson/blob/3.11.9/bench/data.py).

## Final position

rampa earns performance claims and native code by measurement, against a named baseline, using
checks that do not lie about timing. Counts are asserted on every pull request; latency is
measured deliberately, away from the fast path. A faster number that no baseline names is not a
result.
