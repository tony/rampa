"""Threshold expression parser and evaluator for rampa.

Thresholds define pass/fail criteria over metric aggregates. They are the
policy layer — checks measure facts, thresholds decide final status.

>>> import rampa.thresholds
"""

from __future__ import annotations

import operator
import re
import typing as t
from dataclasses import dataclass

from rampa.metrics import Sink

_THRESHOLD_RE = re.compile(
    r"^(count|rate|value|avg|min|max|med|p\(\s*(\d+(?:\.\d+)?)\s*\))"
    r"\s*([<>!=]=?|===?)\s*"
    r"(-?\d+(?:\.\d+)?)$",
)

_SUBMETRIC_RE = re.compile(
    r"^([^{]+)\{([^}]+)\}$",
)

_OPERATORS: dict[str, t.Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "===": operator.eq,
    "!=": operator.ne,
}


@dataclass(frozen=True)
class ThresholdExpression:
    """A parsed threshold expression.

    >>> expr = parse_threshold("p(95)<500")
    >>> expr.aggregation
    'p(95)'
    >>> expr.operator
    '<'
    >>> expr.value
    500.0
    """

    aggregation: str
    aggregation_value: float | None
    operator: str
    value: float


def parse_threshold(expr: str) -> ThresholdExpression:
    """Parse a threshold expression string.

    Parameters
    ----------
    expr : str
        Expression like ``"p(95)<500"``, ``"rate<0.01"``, ``"avg>200"``.

    Returns
    -------
    ThresholdExpression
        Parsed expression.

    Raises
    ------
    ValueError
        If the expression is malformed.

    >>> parse_threshold("count>=100").aggregation
    'count'
    >>> parse_threshold("med<400").value
    400.0
    >>> parse_threshold("p(99.9)<=1000").aggregation
    'p(99.9)'
    >>> parse_threshold("p(99.9)<=1000").aggregation_value
    99.9
    """
    expr = expr.strip()
    match = _THRESHOLD_RE.match(expr)
    if not match:
        msg = f"invalid threshold expression: {expr!r}"
        raise ValueError(msg)

    aggregation = match.group(1)
    percentile_value = match.group(2)
    op = match.group(3)
    value = float(match.group(4))

    agg_value: float | None = None
    if percentile_value is not None:
        agg_value = float(percentile_value)

    return ThresholdExpression(
        aggregation=aggregation,
        aggregation_value=agg_value,
        operator=op,
        value=value,
    )


def parse_submetric(name: str) -> tuple[str, dict[str, str]]:
    """Parse a metric name that may include tag filters.

    Parameters
    ----------
    name : str
        Metric name, optionally with tag filters like
        ``"http_req_duration{status:200}"``.

    Returns
    -------
    tuple[str, dict[str, str]]
        The base metric name and a dict of tag filters.

    >>> parse_submetric("http_req_duration{status:200}")
    ('http_req_duration', {'status': '200'})
    >>> parse_submetric("http_reqs")
    ('http_reqs', {})
    >>> parse_submetric("dur{method:GET,name:login}")
    ('dur', {'method': 'GET', 'name': 'login'})
    """
    match = _SUBMETRIC_RE.match(name)
    if not match:
        return name, {}
    base_name = match.group(1)
    filter_str = match.group(2)
    tags: dict[str, str] = {}
    for pair in filter_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            k, v = pair.split(":", 1)
            tags[k.strip()] = v.strip()
    return base_name, tags


@dataclass
class Threshold:
    """A configured threshold with expression and abort behavior.

    >>> t = Threshold(
    ...     source="p(95)<500",
    ...     expression=parse_threshold("p(95)<500"),
    ... )
    >>> t.abort_on_fail
    False
    """

    source: str
    expression: ThresholdExpression
    abort_on_fail: bool = False
    grace_period: float | None = None
    last_failed: bool = False


@dataclass(frozen=True)
class ThresholdResult:
    """Result of evaluating one threshold.

    >>> r = ThresholdResult(source="p(95)<500", passed=True, lhs=450.0, rhs=500.0)
    >>> r.passed
    True
    """

    source: str
    passed: bool
    lhs: float
    rhs: float


def _sink_key(aggregation: str) -> str:
    """Map threshold aggregation to sink format key."""
    return aggregation


def evaluate_threshold(
    threshold: Threshold,
    sink: Sink,
    duration: float,
) -> ThresholdResult:
    """Evaluate a single threshold against a sink.

    Parameters
    ----------
    threshold : Threshold
        The threshold to evaluate.
    sink : Sink
        The metric sink containing aggregated values.
    duration : float
        Elapsed test duration in seconds.

    Returns
    -------
    ThresholdResult
        Whether the threshold passed.

    >>> from rampa.metrics import TrendSink
    >>> s = TrendSink()
    >>> for v in range(100):
    ...     s.add(float(v))
    >>> t = Threshold(
    ...     source="p(95)<200",
    ...     expression=parse_threshold("p(95)<200"),
    ... )
    >>> evaluate_threshold(t, s, 1.0).passed
    True
    """
    formatted = sink.format(duration)
    key = _sink_key(threshold.expression.aggregation)
    lhs = formatted.get(key, 0.0)
    op_fn = _OPERATORS.get(threshold.expression.operator, operator.lt)
    passed = op_fn(lhs, threshold.expression.value)
    threshold.last_failed = not passed
    return ThresholdResult(
        source=threshold.source,
        passed=passed,
        lhs=lhs,
        rhs=threshold.expression.value,
    )


def evaluate_thresholds(
    metric_thresholds: dict[str, list[Threshold]],
    sinks: dict[str, Sink],
    duration: float,
) -> list[ThresholdResult]:
    """Evaluate all thresholds against their metric sinks.

    Parameters
    ----------
    metric_thresholds : dict[str, list[Threshold]]
        Metric name → list of thresholds for that metric.
    sinks : dict[str, Sink]
        Metric name → sink mapping.
    duration : float
        Elapsed test duration in seconds.

    Returns
    -------
    list[ThresholdResult]
        Results for each threshold.

    >>> from rampa.metrics import CounterSink
    >>> sink = CounterSink()
    >>> sink.add(50.0)
    >>> mt = {"reqs": [Threshold(
    ...     source="count>=100",
    ...     expression=parse_threshold("count>=100"),
    ... )]}
    >>> results = evaluate_thresholds(mt, {"reqs": sink}, 1.0)
    >>> results[0].passed
    False
    """
    results: list[ThresholdResult] = []
    for metric_name, thresholds in metric_thresholds.items():
        base_name, _tag_filter = parse_submetric(metric_name)
        sink = sinks.get(base_name)
        if sink is None:
            results.extend(
                ThresholdResult(
                    source=threshold.source,
                    passed=True,
                    lhs=0.0,
                    rhs=threshold.expression.value,
                )
                for threshold in thresholds
            )
            continue
        results.extend(evaluate_threshold(threshold, sink, duration) for threshold in thresholds)
    return results
