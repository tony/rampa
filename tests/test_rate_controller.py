"""Tests for rate controllers (Python and optional Rust accelerator).

Imports from ``rampa.rate_controller`` which provides Python-first
implementations, optionally accelerated by Rust. Tests must pass
without the Rust extension.
"""

from __future__ import annotations

import typing as t

import pytest

from rampa.rate_controller import RampingRateController, RateController


class RateFixture(t.NamedTuple):
    """Test case for RateController.advance."""

    test_id: str
    start_ns: int
    interval_ns: int
    now_ns: int
    expected_due: int


_RATE_FIXTURES: list[RateFixture] = [
    RateFixture(
        test_id="no_time_elapsed",
        start_ns=0,
        interval_ns=1_000_000,
        now_ns=0,
        expected_due=0,
    ),
    RateFixture(
        test_id="one_tick_due",
        start_ns=0,
        interval_ns=1_000_000,
        now_ns=1_000_000,
        expected_due=1,
    ),
    RateFixture(
        test_id="five_ticks_due",
        start_ns=0,
        interval_ns=1_000_000,
        now_ns=5_000_000,
        expected_due=5,
    ),
    RateFixture(
        test_id="partial_interval",
        start_ns=0,
        interval_ns=1_000_000,
        now_ns=500_000,
        expected_due=0,
    ),
    RateFixture(
        test_id="offset_start",
        start_ns=1_000_000,
        interval_ns=500_000,
        now_ns=3_000_000,
        expected_due=4,
    ),
]


@pytest.mark.parametrize(
    list(RateFixture._fields),
    _RATE_FIXTURES,
    ids=[f.test_id for f in _RATE_FIXTURES],
)
def test_rate_controller_advance(
    test_id: str,
    start_ns: int,
    interval_ns: int,
    now_ns: int,
    expected_due: int,
) -> None:
    """RateController.advance returns correct due count."""
    rc = RateController(start_ns, interval_ns)
    due, _next = rc.advance(now_ns)
    assert due == expected_due


def test_rate_controller_next_deadline() -> None:
    """RateController.advance returns correct next deadline."""
    rc = RateController(0, 1_000_000)
    _due, next_ns = rc.advance(3_500_000)
    assert next_ns == 4_000_000


def test_rate_controller_tick_monotonic() -> None:
    """RateController.tick never decreases across multiple advances."""
    rc = RateController(0, 100_000)
    prev_tick = 0
    for now in range(0, 10_000_000, 350_000):
        rc.advance(now)
        assert rc.tick >= prev_tick
        prev_tick = rc.tick


def test_rate_controller_parity_with_arithmetic() -> None:
    """Rate controller matches pure integer deadline arithmetic."""
    start_ns = 1_000_000_000
    interval_ns = 2_000_000

    rc = RateController(start_ns, interval_ns)
    py_tick = 0

    for step in range(500):
        now_ns = start_ns + step * 750_000
        due, _next = rc.advance(now_ns)

        elapsed = now_ns - start_ns
        py_target_tick = elapsed // interval_ns
        py_due = py_target_tick - py_tick
        py_tick = py_target_tick

        assert due == py_due, f"step {step}: got={due}, expected={py_due}"


def test_rate_controller_interval_ns_property() -> None:
    """RateController.interval_ns returns configured value."""
    rc = RateController(0, 42_000)
    assert rc.interval_ns == 42_000


def test_ramping_rate_controller_basic() -> None:
    """RampingRateController produces iterations during a ramp."""
    rc = RampingRateController(0, 1_000_000_000, 10.0, 100.0, 1_000_000_000.0)
    total_due = 0
    for t_ms in range(0, 1000, 50):
        now = t_ms * 1_000_000
        due, _next = rc.advance(now)
        total_due += due

    assert total_due > 0
    assert rc.tick > 0


def test_ramping_rate_controller_tick_monotonic() -> None:
    """RampingRateController.tick never decreases."""
    rc = RampingRateController(0, 1_000_000_000, 50.0, 200.0, 1_000_000_000.0)
    prev = 0
    for t_ms in range(0, 1000, 10):
        rc.advance(t_ms * 1_000_000)
        assert rc.tick >= prev
        prev = rc.tick


def test_python_implementation_exists() -> None:
    """Python RateController is importable even without Rust."""
    import rampa.rate_controller as mod

    assert hasattr(mod, "RateController")
    assert hasattr(mod, "RampingRateController")
    assert hasattr(mod, "_HAVE_RUST_RATE_CONTROLLER")
    assert isinstance(mod._HAVE_RUST_RATE_CONTROLLER, bool)
