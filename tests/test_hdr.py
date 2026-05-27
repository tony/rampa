"""Tests for the Rust HDR histogram extension and its Python adapter."""

from __future__ import annotations

import typing as t

import pytest

_core = pytest.importorskip("rampa._core", reason="Rust extension not built")


# ---------------------------------------------------------------------------
# Group A: Raw HdrHistogram (Rust class through Python API)
# ---------------------------------------------------------------------------


def test_rust_info_returns_string() -> None:
    """rust_info() returns a non-empty version string."""
    info = _core.rust_info()
    assert isinstance(info, str)
    assert len(info) > 0


def test_hdr_histogram_record_and_count() -> None:
    """HdrHistogram tracks sample count after record()."""
    h = _core.HdrHistogram(3)
    assert h.count() == 0
    h.record(100)
    h.record(200)
    h.record(300)
    assert h.count() == 3


def test_hdr_histogram_record_n_bulk() -> None:
    """HdrHistogram record_n adds count samples at value."""
    h = _core.HdrHistogram(3)
    h.record_n(500, 10)
    assert h.count() == 10
    assert h.min() == 500
    assert h.max() == 500


def test_hdr_histogram_min_max() -> None:
    """HdrHistogram correctly reports min/max values."""
    h = _core.HdrHistogram(3)
    h.record(10)
    h.record(1000)
    h.record(500)
    assert h.min() == 10
    assert h.max() == 1000


def test_hdr_histogram_mean() -> None:
    """HdrHistogram computes arithmetic mean."""
    h = _core.HdrHistogram(3)
    for v in [100, 200, 300]:
        h.record(v)
    assert abs(h.mean() - 200.0) < 1.0


def test_hdr_histogram_stdev() -> None:
    """HdrHistogram computes standard deviation."""
    h = _core.HdrHistogram(3)
    for v in [100, 100, 100]:
        h.record(v)
    assert h.stdev() == pytest.approx(0.0, abs=1.0)

    h2 = _core.HdrHistogram(3)
    for v in [100, 200, 300]:
        h2.record(v)
    assert h2.stdev() > 0


def test_hdr_histogram_percentile_median() -> None:
    """HdrHistogram percentile(50) returns median."""
    h = _core.HdrHistogram(3)
    for v in range(1, 101):
        h.record(v)
    med = h.percentile(50.0)
    assert 49 <= med <= 51


def test_hdr_histogram_reset_clears_state() -> None:
    """HdrHistogram reset() discards all recorded values."""
    h = _core.HdrHistogram(3)
    for v in range(100):
        h.record(v)
    assert h.count() == 100
    h.reset()
    assert h.count() == 0
    assert h.min() == 0
    assert h.max() == 0


def test_hdr_histogram_format_stats_tuple() -> None:
    """format_stats returns (count, mean, min, max, med, p90, p95, p99)."""
    h = _core.HdrHistogram(3)
    for v in [1000, 2000, 3000, 4000, 5000]:
        h.record(v)
    stats = h.format_stats()
    assert len(stats) == 8
    count, mean, mn, mx, med, p90, p95, p99 = stats
    assert count == 5
    assert 999 <= mn <= 1001
    assert 4990 <= mx <= 5010
    assert abs(mean - 3000.0) < 10.0
    assert 2900 <= med <= 3100
    assert p99 >= p90
    assert p95 >= p90


def test_hdr_histogram_invalid_sigfig_raises() -> None:
    """HdrHistogram rejects sigfig > 5 with ValueError."""
    with pytest.raises(ValueError):
        _core.HdrHistogram(6)


# ---------------------------------------------------------------------------
# Group B: HdrTrendSink (Python adapter)
# ---------------------------------------------------------------------------


def test_hdr_trend_sink_add_format_cycle() -> None:
    """HdrTrendSink.add() accepts float ms, format() returns stats dict."""
    from rampa.metrics import HdrTrendSink

    s = HdrTrendSink()
    for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
        s.add(v)
    fmt = s.format(1.0)
    assert fmt["count"] == 5.0
    assert fmt["min"] == pytest.approx(10.0, rel=0.01)
    assert fmt["max"] == pytest.approx(50.0, rel=0.01)
    assert fmt["avg"] == pytest.approx(30.0, rel=0.01)


def test_hdr_trend_sink_empty_format() -> None:
    """HdrTrendSink.format() returns all-zero dict when empty."""
    from rampa.metrics import HdrTrendSink

    s = HdrTrendSink()
    fmt = s.format(1.0)
    assert all(v == 0.0 for v in fmt.values())


def test_hdr_trend_sink_keys_match_python_sink() -> None:
    """HdrTrendSink.format() returns same keys as TrendSink.format()."""
    from rampa.metrics import HdrTrendSink, TrendSink

    hdr = HdrTrendSink()
    py = TrendSink()
    for v in [1.0, 2.0, 3.0]:
        hdr.add(v)
        py.add(v)
    assert set(hdr.format(1.0).keys()) == set(py.format(1.0).keys())


# ---------------------------------------------------------------------------
# Group C: Parametrized conversion accuracy
# ---------------------------------------------------------------------------


class ConversionFixture(t.NamedTuple):
    """Test case for HdrTrendSink ms-to-us round-trip accuracy."""

    test_id: str
    input_ms: list[float]
    check_key: str
    expected_approx: float
    tolerance: float


_CONVERSION_FIXTURES: list[ConversionFixture] = [
    ConversionFixture("single_1ms", [1.0], "min", 1.0, 0.002),
    ConversionFixture("single_100ms", [100.0], "max", 100.0, 0.2),
    ConversionFixture("avg_mixed", [10.0, 20.0, 30.0], "avg", 20.0, 0.1),
    ConversionFixture("med_5_values", [10.0, 20.0, 30.0, 40.0, 50.0], "med", 30.0, 0.1),
    ConversionFixture("p90_100_values", [float(i) for i in range(1, 101)], "p(90)", 90.0, 1.5),
]


@pytest.mark.parametrize(
    list(ConversionFixture._fields),
    _CONVERSION_FIXTURES,
    ids=[f.test_id for f in _CONVERSION_FIXTURES],
)
def test_hdr_trend_sink_conversion(
    test_id: str,
    input_ms: list[float],
    check_key: str,
    expected_approx: float,
    tolerance: float,
) -> None:
    """HdrTrendSink preserves value fidelity through ms-to-us round-trip."""
    from rampa.metrics import HdrTrendSink

    s = HdrTrendSink()
    for v in input_ms:
        s.add(v)
    fmt = s.format(1.0)
    assert abs(fmt[check_key] - expected_approx) <= tolerance, (
        f"{check_key}={fmt[check_key]}, expected ~{expected_approx} ±{tolerance}"
    )


# ---------------------------------------------------------------------------
# Group D: Integration proofs (auto-build worked)
# ---------------------------------------------------------------------------


def test_native_extension_importable() -> None:
    """rampa._core is importable after conftest auto-build."""
    from rampa._core import HdrHistogram, rust_info

    assert callable(rust_info)
    h = HdrHistogram(3)
    h.record(42)
    assert h.count() == 1


def test_hdr_trend_sink_uses_rust_backend() -> None:
    """HdrTrendSink wraps the Rust HdrHistogram, not a Python list."""
    from rampa._core import HdrHistogram
    from rampa.metrics import HdrTrendSink

    s = HdrTrendSink()
    assert isinstance(s._hdr, HdrHistogram)


def test_create_sink_non_trend_unaffected() -> None:
    """create_sink for COUNTER/GAUGE/RATE does not return HdrTrendSink."""
    from rampa._types import MetricType
    from rampa.metrics import HdrTrendSink, create_sink

    for mt in [MetricType.COUNTER, MetricType.GAUGE, MetricType.RATE]:
        sink = create_sink(mt)
        assert not isinstance(sink, HdrTrendSink)
