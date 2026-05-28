# ADR 001: Pure Python/Rust Accelerator Module Compatibility Requirements

Status: Accepted
Date: 2026-05-28

## Context

This project is a Python project that may use Rust to accelerate selected modules, functions, or classes.

Native acceleration creates a compatibility risk: the Rust implementation can accidentally become the real implementation, while the Python implementation becomes incomplete, stale, or semantically different. That harms portability, testability, and user trust. It can also make the project harder to install in environments without a Rust toolchain or without compatible binary wheels.

Python's standard library has a similar policy in PEP 399 for pure Python modules with native accelerators. This ADR adapts that idea for this project: pure Python remains the reference implementation, and Rust exists as an optional drop-in accelerator.

## Decision

Every public API must have a pure Python implementation unless this project explicitly grants an exemption.

The pure Python implementation is the semantic source of truth. Rust acceleration may be added for performance, but it must behave as a drop-in replacement for the Python implementation as far as reasonably possible.

The Rust accelerator must pass the same behavioral tests as the pure Python implementation. Rust-specific tests may be added, but they do not replace shared compatibility tests.

The package must remain usable without the Rust extension.

## Scope

This ADR applies to:

- Public functions
- Public classes
- Public methods and attributes
- Public constants whose value or type is part of the API contract
- Public module behavior
- Serialization, equality, hashing, ordering, iteration, context-manager, and async behavior where relevant
- Error behavior that users can observe

This ADR also applies to private Rust code when that code affects public behavior.

## Requirements

### 1. Pure Python first

New public behavior must be implemented in Python before it is accelerated in Rust.

Rust must not be the only implementation of a public API unless an exemption is approved and documented.

Acceptable exemption cases are narrow. Examples include:

- APIs whose only purpose is to expose a Rust-only subsystem.
- Functionality that cannot reasonably be implemented in Python.
- Internal diagnostics, build hooks, or development-only helpers that are not public API.

Exemptions must be documented in the pull request and in the relevant module or package documentation.

### 2. Rust as companion accelerator

Rust acceleration is a companion implementation, not an independent API surface.

Rust may replace selected Python functions, classes, or internals only after the Python implementation has defined the expected public behavior.

Rust must not introduce:

- New public functions
- New public classes
- New public methods or attributes
- New accepted argument forms
- New return shapes
- Different validation rules
- Different mutation side effects
- Different ordering, equality, hashing, or serialization behavior
- Different exception classes for the same invalid input, unless approved and documented

### 3. Optional accelerator

The project must import and run without the Rust extension.

When the Rust extension is unavailable, the package should fall back to Python:

```python
from ._module_py import parse, normalize

_HAS_RUST_ACCELERATOR = False

try:
    from ._native import parse as parse
    from ._native import normalize as normalize
except ImportError:
    pass
else:
    _HAS_RUST_ACCELERATOR = True
```

Fallback code should catch `ImportError`, not broad `Exception`, unless there is a specific and documented reason. Tests should not hide unexpected Rust import failures.

### 4. Shared compatibility tests

Every accelerated API must be tested against both implementations.

The shared test suite must run against:

1. The pure Python implementation with Rust disabled or absent.
2. The Rust-accelerated implementation when Rust is available.

Recommended `pytest` structure:

```python
import pytest

from package_name import _module_py

try:
    from package_name import _native
except ImportError:
    _native = None


@pytest.fixture(params=[_module_py, _native], ids=["python", "rust"])
def impl(request):
    if request.param is None:
        pytest.skip("Rust accelerator is not available")
    return request.param


def test_empty_input(impl):
    assert impl.parse("") == []


def test_invalid_input(impl):
    with pytest.raises(ValueError):
        impl.parse("\x00")
```

Tests must cover the behavior users rely on, including:

- Normal inputs
- Empty inputs
- Boundary values
- Invalid inputs
- Subclasses and duck-typed inputs where relevant
- Mutation and aliasing behavior
- Repeated calls
- Large inputs
- Unicode or binary edge cases where relevant
- Error paths
- Resource cleanup paths
- Serialization, equality, hashing, ordering, iteration, context-manager, or async behavior where relevant

### 5. Duck typing preservation

Rust must preserve the input contract of the Python implementation.

If Python accepts any iterable, mapping, sequence, path-like object, buffer-like object, subclass, or file-like object, Rust must not narrow that behavior to a concrete type only.

Fast paths are allowed, but they must retain a correct generic path.

Acceptable:

```text
Rust uses a fast path for list[str], then falls back to generic iterable handling.
```

Unacceptable:

```text
Python accepts any iterable[str], but Rust accepts only list[str].
```

### 6. Error behavior

Rust must raise the same Python exception classes as the Python implementation wherever practical.

Rust panics must not cross the Python FFI boundary. Internal Rust errors must be converted into Python exceptions.

The compatibility tests must verify important error paths.

### 7. Documentation and type hints

Public documentation describes the public Python API, not the Rust implementation.

Type hints, overloads, and stubs must remain accurate for the public API regardless of whether Rust is installed.

Rust-only signatures must not leak into user-facing documentation or stubs.

### 8. Packaging

The package must remain usable in environments without a Rust compiler or compatible native wheel unless the project explicitly approves a Rust-required feature.

Packaging must support:

- Python-only operation
- Rust-accelerated operation when available
- Clear fallback behavior
- No import-time failure solely because Rust is unavailable

### 9. CI

CI must include both code paths.

Minimum required jobs:

```text
Python-only job:
  - install without Rust or force the Python fallback
  - run the full shared behavioral test suite

Rust-enabled job:
  - build/install the Rust extension
  - run the same shared behavioral test suite
  - run Rust-specific tests, if any
```

The Python-only job is mandatory. A passing Rust-enabled job does not compensate for a failing Python-only job.

### 10. Unsafe Rust

`unsafe` Rust is allowed only when necessary.

Every `unsafe` block must have a nearby `SAFETY:` comment explaining:

1. Why `unsafe` is needed.
2. What invariants make it sound.
3. How those invariants are enforced.
4. Which tests cover the relevant edge cases, when applicable.

Example:

```rust
// SAFETY:
// `idx` is checked against `items.len()` immediately above.
// `items` is not mutated between the bounds check and access.
unsafe {
    items.get_unchecked(idx)
}
```

## Consequences

### Positive consequences

- The project remains portable across environments where Rust is unavailable.
- Users receive the same behavior whether or not acceleration is installed.
- The Python implementation remains complete and useful for debugging, documentation, and alternative runtimes.
- Rust acceleration can be added without creating a second public API.
- CI detects semantic drift between Python and Rust implementations.

### Tradeoffs

- Contributors must maintain two implementations for accelerated behavior.
- Tests must be structured to exercise both paths.
- Some performance optimizations may be rejected if they narrow Python semantics.
- Build and packaging workflows must account for both Python-only and Rust-enabled modes.

### Risks

The main risk is semantic drift: Rust and Python implementations may diverge over time. The mitigation is mandatory shared compatibility testing and Python-first development.

Another risk is hidden fallback: broad exception handling can mask Rust defects. The mitigation is narrow import fallback in runtime code and stricter behavior in tests.

## Implementation guidance

Preferred module layout:

```text
src/
  package_name/
    __init__.py
    module.py          # public API and accelerator selection
    _module_py.py      # pure Python reference implementation
    _native.*          # compiled Rust extension artifact
rust/
  Cargo.toml
  src/
    lib.rs
tests/
  test_module.py
  test_module_compat.py
```

Preferred public-module pattern:

```python
from ._module_py import Token, parse, normalize

_HAS_RUST_ACCELERATOR = False

try:
    from ._native import parse as parse
    from ._native import normalize as normalize
except ImportError:
    pass
else:
    _HAS_RUST_ACCELERATOR = True
```

Public Rust-only names must not be re-exported from the public module.

## Pull request checklist

A pull request that adds or modifies Rust acceleration must confirm:

```text
[ ] Public behavior exists first in pure Python.
[ ] Shared tests cover the Python implementation.
[ ] The same shared tests pass with Rust enabled.
[ ] The package imports and runs without Rust.
[ ] Rust exposes no extra public API.
[ ] Rust preserves duck-typed inputs accepted by Python.
[ ] Rust error behavior matches Python error behavior.
[ ] Type hints and documentation remain accurate.
[ ] Packaging impact is described.
[ ] Benchmarks or a clear performance rationale justify the accelerator.
[ ] Unsafe Rust, if any, is documented with SAFETY comments.
```

## Final position

Rust may make this project faster. Rust must not make the project less Pythonic, less portable, less tested, less predictable, or less compatible.

The Python implementation defines the meaning of the public API. The Rust implementation may make that meaning faster.
