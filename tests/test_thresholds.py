"""Tests for rampa threshold parsing and evaluation."""

from __future__ import annotations

import typing as t

import pytest

from rampa.metrics import CounterSink, RateSink, TrendSink
from rampa.thresholds import (
    Threshold,
    evaluate_threshold,
    evaluate_thresholds,
    parse_submetric,
    parse_threshold,
)


class ParseFixture(t.NamedTuple):
    """Test case for parse_threshold()."""

    test_id: str
    expr: str
    aggregation: str
    operator: str
    value: float
    agg_value: float | None


_PARSE_FIXTURES: list[ParseFixture] = [
    ParseFixture("p95_lt", "p(95)<500", "p(95)", "<", 500.0, 95.0),
    ParseFixture("rate_lt", "rate<0.01", "rate", "<", 0.01, None),
    ParseFixture("count_gte", "count>=100", "count", ">=", 100.0, None),
    ParseFixture("avg_gt", "avg>200", "avg", ">", 200.0, None),
    ParseFixture("med_lt", "med<400", "med", "<", 400.0, None),
    ParseFixture("min_gte", "min>=0", "min", ">=", 0.0, None),
    ParseFixture("max_lte", "max<=3000", "max", "<=", 3000.0, None),
    ParseFixture("value_eq", "value==42", "value", "==", 42.0, None),
    ParseFixture("p99_lte", "p(99)<=1000", "p(99)", "<=", 1000.0, 99.0),
    ParseFixture(
        "p99_9",
        "p(99.9)<=1000",
        "p(99.9)",
        "<=",
        1000.0,
        99.9,
    ),
    ParseFixture("ne", "count!=0", "count", "!=", 0.0, None),
    ParseFixture("spaces", " p(95) < 500 ", "p(95)", "<", 500.0, 95.0),
]


@pytest.mark.parametrize(
    list(ParseFixture._fields),
    _PARSE_FIXTURES,
    ids=[f.test_id for f in _PARSE_FIXTURES],
)
def test_parse_threshold(
    test_id: str,
    expr: str,
    aggregation: str,
    operator: str,
    value: float,
    agg_value: float | None,
) -> None:
    """parse_threshold() extracts aggregation, operator, and value."""
    result = parse_threshold(expr)
    assert result.aggregation == aggregation
    assert result.operator == operator
    assert result.value == value
    assert result.aggregation_value == agg_value


class InvalidExprFixture(t.NamedTuple):
    """Test case for invalid threshold expressions."""

    test_id: str
    expr: str


_INVALID_EXPRS: list[InvalidExprFixture] = [
    InvalidExprFixture("empty", ""),
    InvalidExprFixture("no_op", "p(95)500"),
    InvalidExprFixture("bad_agg", "foo<500"),
    InvalidExprFixture("no_value", "p(95)<"),
    InvalidExprFixture("text_value", "avg<fast"),
]


@pytest.mark.parametrize(
    list(InvalidExprFixture._fields),
    _INVALID_EXPRS,
    ids=[f.test_id for f in _INVALID_EXPRS],
)
def test_parse_threshold_rejects_invalid(
    test_id: str,
    expr: str,
) -> None:
    """parse_threshold() raises ValueError for bad input."""
    with pytest.raises(ValueError, match="invalid threshold"):
        parse_threshold(expr)


def test_parse_submetric_with_tags() -> None:
    """parse_submetric() extracts metric name and tag filters."""
    name, tags = parse_submetric("http_req_duration{status:200}")
    assert name == "http_req_duration"
    assert tags == {"status": "200"}


def test_parse_submetric_multiple_tags() -> None:
    """parse_submetric() handles multiple comma-separated tags."""
    name, tags = parse_submetric("dur{method:GET,name:login}")
    assert name == "dur"
    assert tags == {"method": "GET", "name": "login"}


def test_parse_submetric_no_tags() -> None:
    """parse_submetric() returns empty tags for plain metric names."""
    name, tags = parse_submetric("http_reqs")
    assert name == "http_reqs"
    assert tags == {}


def test_evaluate_threshold_passes() -> None:
    """evaluate_threshold() returns passed=True when condition met."""
    sink = TrendSink()
    for v in range(100):
        sink.add(float(v))
    t = Threshold(
        source="p(95)<200",
        expression=parse_threshold("p(95)<200"),
    )
    result = evaluate_threshold(t, sink, 1.0)
    assert result.passed is True
    assert result.lhs < 200.0


def test_evaluate_threshold_fails() -> None:
    """evaluate_threshold() returns passed=False when condition not met."""
    sink = TrendSink()
    for v in range(100):
        sink.add(float(v) * 10)
    t = Threshold(
        source="p(95)<100",
        expression=parse_threshold("p(95)<100"),
    )
    result = evaluate_threshold(t, sink, 1.0)
    assert result.passed is False


def test_evaluate_thresholds_multiple() -> None:
    """evaluate_thresholds() evaluates all thresholds for each metric."""
    counter = CounterSink()
    counter.add(50.0)
    rate = RateSink()
    rate.add(1.0)
    rate.add(0.0)

    mt = {
        "reqs": [
            Threshold(
                source="count>=100",
                expression=parse_threshold("count>=100"),
            ),
        ],
        "checks": [
            Threshold(
                source="rate>0.99",
                expression=parse_threshold("rate>0.99"),
            ),
        ],
    }

    results = evaluate_thresholds(
        mt,
        {"reqs": counter, "checks": rate},
        1.0,
    )
    assert len(results) == 2
    reqs_result = results[0]
    assert reqs_result.passed is False
    checks_result = results[1]
    assert checks_result.passed is False


def test_evaluate_thresholds_missing_sink() -> None:
    """evaluate_thresholds() passes when the metric sink is missing."""
    mt = {
        "nonexistent": [
            Threshold(
                source="count>=0",
                expression=parse_threshold("count>=0"),
            ),
        ],
    }
    results = evaluate_thresholds(mt, {}, 1.0)
    assert len(results) == 1
    assert results[0].passed is True
