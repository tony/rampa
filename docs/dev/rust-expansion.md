(rust-expansion)=
# Rust expansion

rampa uses optional Rust extensions via [PyO3](https://pyo3.rs/) and
[maturin](https://www.maturin.rs/) to accelerate performance-critical paths.
Rust is not a design goal — it is a tool used only where benchmarks prove
Python is the limiting factor.

## Architecture boundary

Rust owns mechanical hot paths: timers, queues, counters, histograms, tag
matching, batch ingest. Python owns user-facing API, scenario loading,
orchestration, CLI, outputs, and policy (thresholds, checks).

```text
┌─────────────────────────────────────────────┐
│  Python (user-facing)                       │
│  scenarios, executors, CLI, TUI, MCP,       │
│  outputs, thresholds, EventBus              │
├─────────────────────────────────────────────┤
│  rampa._core (optional Rust via PyO3)       │
│  HdrHistogram, RateController,              │
│  RampingRateController                      │
└─────────────────────────────────────────────┘
```

## Current Rust components

{class}`~rampa._core.HdrHistogram`
: Fixed ~20 KB memory HDR histogram for O(1) percentile computation.
  Used by {class}`~rampa.metrics.HdrTrendSink` when available.

{class}`~rampa._core.RateController`
: Integer-arithmetic deadline calculator for constant arrival-rate
  executors. Eliminates cumulative float drift.

{class}`~rampa._core.RampingRateController`
: ``f64`` ramp interpolation with trapezoidal integration for ramping
  arrival-rate executors.

## Fallback strategy

Every Rust component has a Python fallback. The pattern:

```python
_USE_RUST_RATE: bool = False
try:
    from rampa._core import RateController
    _USE_RUST_RATE = True
except ImportError:
    pass
```

The `conftest.py` auto-build hook runs `maturin develop --uv` during test
collection so developers with Rust get the fast path automatically. CI
tests both paths.

## Building the extension

```console
$ uv run maturin develop --uv
```

The extension is built automatically during test collection. To build
a release wheel:

```console
$ uv run maturin build --release
```
