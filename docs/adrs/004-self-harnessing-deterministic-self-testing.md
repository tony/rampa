(adr-004-self-harnessing-deterministic-self-testing)=

# ADR 004: Self-Harnessing — Deterministic Self-Testing of the Load Generator

Status: Proposed
Date: 2026-05-29

## Context

ADR 001 requires that every accelerated public API have a pure-Python reference and that the
same behavioral suite pass on both the pure-Python and the native path. ADR 002 and ADR 003 add
that the base package must install, import, and run without native code, and that native code
must never change what a load test measures. Those rules are only as good as the test suite that
enforces them.

rampa is a load generator: its correctness is not "does the function return the right value" but
"did it schedule the right work, at the right time, classify outcomes correctly, and aggregate
them faithfully." A test that imports a module and asserts it is not None proves almost nothing
about that. Worse, a load generator's own behavior is timing- and concurrency-dependent, so a
naive suite is either flaky (real sleeps, real clocks, real ports) or vacuous (mocks so deep the
scheduler never runs).

This ADR defines rampa's **self-harness**: the discipline of testing the framework by running it
end-to-end against a controllable target and asserting exact, observable outcomes, deterministically,
on both implementation paths. It is the foundation the self-benchmarking (ADR 005) and
self-profiling (ADR 006) policies measure against.

## Decision

rampa maintains a deterministic self-harness. Tests exercise the framework end-to-end against an
in-process target, assert exact observable outcomes, run against both the pure-Python and the
native path, and are deterministic by construction rather than by luck.

"Ran without raising" is not a passing load-test. A test asserts what the run produced: how many
requests went where, what the metrics aggregated to, which thresholds passed, and how failures
were classified.

## Scope

This ADR governs rampa's own test suite and test infrastructure. It applies to:

- End-to-end runs of executors, the scheduler, the metric engine, thresholds, and protocol clients.
- The shared behavioral suite that must pass on both implementation paths (the operational form
  of ADR 001 §4).
- Determinism, isolation, and leak-detection mechanics for the suite.

It does not govern what is benchmarked (ADR 005) or profiled (ADR 006), though it provides the
harness both reuse.

## Requirements

### 1. End-to-end against a controllable target

Behavioral tests drive a real run against an in-process mock server (or loopback target) and
assert exact outcomes: per-target request and iteration counts, metric aggregates, threshold
verdicts, and failure classification. The scheduler, metric engine, and protocol client must
actually execute; mocking is confined to the target under load, not rampa's internals.

Goose demonstrates this end-to-end posture: its scheduler tests assert exact mock hit counts
(`assert_calls(USERS * 2)`) to prove the right work was dispatched to the right users, driven
through a real in-process mock server.
See [`tests/scheduler.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/tests/scheduler.rs)
and the shared harness in [`tests/common.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/tests/common.rs).

### 2. Both paths, every run

The shared behavioral suite runs against both implementations via a parametrized fixture
(`params=[python, native]`, per ADR 001 §4). CI runs the mandatory Python-only job with the
native extension absent, alongside the native-enabled job. A green native job never substitutes
for a green Python-only job.

SQLAlchemy runs its full suite both with and without its compiled C extensions on every build,
selected by environment flags in its test plugin
([`lib/sqlalchemy/testing/plugin/plugin_base.py`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/testing/plugin/plugin_base.py)).
CPython's accelerated stdlib modules share one test suite with their pure-Python reference.

### 3. Deterministic by construction

Timing-sensitive behavior is tested with an injected, controllable monotonic clock rather than
real `sleep`. Randomness is seeded. Ephemeral ports are bound and tests that bind ports or mutate
global state are serialized. A test must fail because behavior changed, not because a machine was
busy.

### 4. Leak and stability check

Long-running paths (connection pools, metric buffers, sub-sinks) have a repeat-and-diff check:
run an operation N times in subprocess isolation and assert a resource counter flatlines rather
than asserting an absolute number. CPython's regression runner hunts reference leaks this way,
re-running each test and diffing a counter
([`Lib/test/libregrtest/refleak.py`](https://github.com/python/cpython/blob/v3.14.5/Lib/test/libregrtest/refleak.py)).

### 5. Scheduler ordering (aspirational)

Where feasible, exercise concurrent scheduling orderings deterministically — stepping the event
loop against a frozen clock — rather than trusting wall-clock races. This is the asyncio analog
of the model-checking Rust runtimes use: tokio swaps `std::sync` for a model checker behind a
`cfg(loom)` gate and explores interleavings in a dedicated, bounded, sharded CI job
([`tokio/src/loom/mod.rs`](https://github.com/tokio-rs/tokio/blob/tokio-1.52.3/tokio/src/loom/mod.rs),
[`.github/workflows/loom.yml`](https://github.com/tokio-rs/tokio/blob/tokio-1.52.3/.github/workflows/loom.yml));
crossbeam drives the same from a checked-in script with an explicit preemption budget
([`ci/crossbeam-epoch-loom.sh`](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-0.8.4/ci/crossbeam-epoch-loom.sh)).
Full interleaving model-checking is not available in CPython today; the requirement is the
discipline (controlled stepping, frozen clock), not the specific tool.

### 6. Fixtures as specification

Harness scenarios are treated as a living specification, including negative "fails cleanly"
cases (unsupported feature rejected before run, invalid config, timeout/cancellation), not only
happy paths. Maturin treats its ~40 `test-crates/` fixtures as first-class architecture spanning
the combinatorial surface including negative cases
([`test-crates/`](https://github.com/PyO3/maturin/tree/v1.13.3/test-crates)); pytest exposes its
own self-test harness, `pytester`, as a public utility
([`src/_pytest/pytester.py`](https://github.com/pytest-dev/pytest/blob/9.0.3/src/_pytest/pytester.py)).

## Self-harness record

A pull request that adds or changes observable load-generation behavior records:

```text
test surface:            scenario | scheduler | metrics | thresholds | protocol | end-to-end
target:                  in-process mock | loopback server | external (cite)
both paths:              python-only run + native-enabled run (params=[python, native])
asserted outcomes:       request/iteration counts | metric aggregates | threshold verdicts | errors
clock source:            injected monotonic | frozen | real (justify)
determinism controls:    seeded RNG | pinned ports | serialized global-state tests
leak/stability check:    none | repeat-and-diff object/refcount in subprocess
negative cases:          unsupported feature rejected | invalid config | timeout/cancel
```

## Pull request checklist

```text
[ ] New observable behavior has an end-to-end harness assertion, not just a smoke import.
[ ] The shared behavioral suite runs against both the pure-Python and native paths.
[ ] CI runs the mandatory Python-only job with native absent.
[ ] Timing-sensitive assertions use an injected/controllable clock, not real sleeps.
[ ] Tests that bind ports or touch global state are serialized.
[ ] Long-run paths have a repeat-and-diff leak/stability check.
[ ] Negative ("fails cleanly") cases are covered.
```

## Consequences

### Positive

- ADR 001's "same suite on both paths" stops being aspirational and becomes a CI requirement.
- Load-test correctness (scheduling, classification, aggregation) is actually asserted, not
  assumed.
- Determinism removes the flakiness that otherwise pushes a load-test suite toward vacuous mocks.
- Leak detection guards the long-running paths a load generator actually stresses.

### Tradeoffs

- An end-to-end harness with an injectable clock and a mock target is more infrastructure than a
  unit suite.
- Running every behavioral test twice (both paths) costs CI time.
- Deterministic scheduling tests require controllable seams in the runtime.

### Risks

- Over-mocking: a harness that stubs rampa's internals proves nothing. Mitigation: mock the
  target, run the framework.
- Hidden Python-only failures: if CI only runs the native path, drift goes unnoticed. Mitigation:
  the Python-only job is mandatory (ADR 001 §9).

## Relationship to ADR 001, 002, and 003

ADR 001 requires the dual-path behavioral suite; this ADR specifies the harness that runs it and
the determinism that keeps it honest. ADR 002 and ADR 003 require the base package to work
without native code and forbid silent measurement changes; the Python-only job and the
exact-outcome assertions here are how that is enforced. ADR 005 and ADR 006 reuse this harness as
the surface they benchmark and profile.

## Prior art

- **goose** (`tag1consulting/goose@0.18.1`) — in-process mock-server harness with exact
  call-count scheduler assertions and a coordinated-omission test harness:
  [`tests/scheduler.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/tests/scheduler.rs),
  [`tests/common.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/tests/common.rs),
  [`tests/coordinated_omission_integration.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/tests/coordinated_omission_integration.rs),
  [`src/metrics.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/metrics.rs).
- **SQLAlchemy** (`zzzeek/sqlalchemy@rel_2_0_50`) — runs the suite with and without C extensions
  every build:
  [`lib/sqlalchemy/testing/plugin/plugin_base.py`](https://github.com/zzzeek/sqlalchemy/blob/rel_2_0_50/lib/sqlalchemy/testing/plugin/plugin_base.py).
- **CPython** (`python/cpython@v3.14.5`) — reference-leak hunting by repeat-and-diff and a curated
  test workload:
  [`Lib/test/libregrtest/refleak.py`](https://github.com/python/cpython/blob/v3.14.5/Lib/test/libregrtest/refleak.py),
  [`Lib/test/libregrtest/pgo.py`](https://github.com/python/cpython/blob/v3.14.5/Lib/test/libregrtest/pgo.py).
- **pytest** (`pytest-dev/pytest@9.0.3`) — `pytester`, a self-test harness exposed as a public
  fixture:
  [`src/_pytest/pytester.py`](https://github.com/pytest-dev/pytest/blob/9.0.3/src/_pytest/pytester.py).
- **maturin** (`PyO3/maturin@v1.13.3`) — fixtures-as-specification across a combinatorial surface:
  [`test-crates/`](https://github.com/PyO3/maturin/tree/v1.13.3/test-crates).
- **ruff** (`astral-sh/ruff@0.15.14`) — markdown-driven literate test corpus (`mdtest`):
  [`crates/ty_test/`](https://github.com/astral-sh/ruff/tree/0.15.14/crates/ty_test).
- **tokio** (`tokio-rs/tokio@tokio-1.52.3`) and **crossbeam**
  (`crossbeam-rs/crossbeam@crossbeam-0.8.4`) — deterministic concurrency model-checking behind a
  `cfg(loom)` gate, label-gated and budget-bounded in CI:
  [`tokio/src/loom/mod.rs`](https://github.com/tokio-rs/tokio/blob/tokio-1.52.3/tokio/src/loom/mod.rs),
  [`.github/workflows/loom.yml`](https://github.com/tokio-rs/tokio/blob/tokio-1.52.3/.github/workflows/loom.yml),
  [`tokio/src/runtime/tests/loom_multi_thread.rs`](https://github.com/tokio-rs/tokio/blob/tokio-1.52.3/tokio/src/runtime/tests/loom_multi_thread.rs),
  [`ci/crossbeam-epoch-loom.sh`](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-0.8.4/ci/crossbeam-epoch-loom.sh),
  [`crossbeam-utils/src/lib.rs`](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-0.8.4/crossbeam-utils/src/lib.rs).

## Final position

rampa proves its own correctness by running itself against a controllable target and asserting
exact outcomes, deterministically, on both paths. A load generator that is not harnessed this way
cannot honestly claim to measure anything.
