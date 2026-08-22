(rust-expansion)=
# Rust expansion

rampa uses optional Rust extensions via [PyO3](https://pyo3.rs/) and
[maturin](https://www.maturin.rs/) to accelerate performance-critical paths.
Rust is not a design goal — it is a tool used only where benchmarks prove
Python is the limiting factor.

## PEP 399-like rule

Accelerators must be API-exact accelerators of the Python implementation,
not separate products. The pattern follows CPython's `_json` → `json`
approach: Python classes are defined first, then conditionally replaced
by Rust at import time.

```python
class RateController:
    """Python implementation."""
    ...

try:
    from rampa._core import RateController as RateController
    _HAVE_RUST_RATE_CONTROLLER: bool = True
except ImportError:
    _HAVE_RUST_RATE_CONTROLLER: bool = False
```

Users always import from the public module (e.g. ``rampa.rate_controller``)
and get whichever implementation is available. No code should import
from ``rampa._core`` directly outside of feature-detection blocks.

## Architecture boundary

```text
┌─────────────────────────────────────────────┐
│  Python (user-facing)                       │
│  scenarios, executors, CLI, TUI, MCP,       │
│  outputs, thresholds, EventBus              │
├─────────────────────────────────────────────┤
│  rampa._core (optional Rust via PyO3)       │
│  HdrHistogram, RateController,              │
│  RampingRateController, MetricCore          │
└─────────────────────────────────────────────┘
```

## Compliant accelerators

These follow the PEP 399-like rule with Python-first implementations.

{class}`~rampa._core.HdrHistogram`
: Fixed ~20 KB memory HDR histogram for O(1) percentile computation.
  Accelerates {class}`~rampa.metrics.TrendSink` via
  {class}`~rampa.metrics.HdrTrendSink`. Dispatched through
  {func}`~rampa.metrics.create_sink`.

{class}`~rampa._core.RateController`
: Integer-arithmetic deadline calculator for constant arrival-rate
  executors. Accelerates the Python ``RateController`` in
  {mod}`rampa.rate_controller`.

{class}`~rampa._core.RampingRateController`
: ``f64`` ramp interpolation for ramping arrival-rate executors.
  Accelerates the Python ``RampingRateController`` in
  {mod}`rampa.rate_controller`.

## Experimental components

{class}`~rampa._core.MetricCore`
: Rust metric aggregation core with bounded channel and all sinks
  in Rust. This is an **experimental spike** proving the native boundary
  — it is not yet a PEP 399-compliant accelerator of
  {class}`~rampa.metrics.MetricEngine`. Parity tests exist but it is
  not wired into production code. The ``_HAVE_RUST_METRIC_CORE``
  flag in {mod}`rampa.metrics` indicates availability.

## Adding a new accelerator

1. Write the Python implementation first with full tests and doctests.
2. Write the Rust equivalent with identical API (methods, properties, return types).
3. Add ``#[getter]`` for Python ``@property`` attributes in Rust.
4. Update ``src/rampa/_core.pyi`` with type stubs (use ``@property`` not methods).
5. In the Python module, define the Python class first, then conditionally
   replace it with the Rust import.
6. Add parity tests that pass without Rust.
7. Add benchmark coverage showing the improvement.

## Building the extension

```console
$ uv run maturin develop --uv
```

The extension is built automatically during test collection. To build
a release wheel:

```console
$ uv run maturin build --release
```
