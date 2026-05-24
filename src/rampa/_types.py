"""Core data types for the rampa load testing framework.

This module defines the hot-path types used throughout rampa. These types are
allocated millions of times during a test run, so they use lightweight Python
primitives (NamedTuple, enum) rather than validation-heavy models.

>>> import rampa._types
"""

from __future__ import annotations

import enum
import time
import typing as t


class MetricType(enum.Enum):
    """Classification of a metric's aggregation behavior.

    Each metric type determines which sink accumulates samples and which
    aggregations are available for thresholds and summaries.

    >>> MetricType.COUNTER.value
    'counter'
    >>> MetricType.TREND.value
    'trend'
    """

    COUNTER = "counter"
    GAUGE = "gauge"
    RATE = "rate"
    TREND = "trend"


class ValueType(enum.Enum):
    """Unit hint for metric display formatting.

    >>> ValueType.TIME.value
    'time'
    >>> ValueType.DEFAULT.value
    'default'
    """

    DEFAULT = "default"
    TIME = "time"
    DATA = "data"


class Sample(t.NamedTuple):
    """A single metric observation emitted by a worker or protocol client.

    Samples are the hot-path data type. Every HTTP request produces multiple
    samples (one per timing phase). Construction must be as cheap as possible.

    Parameters
    ----------
    metric : str
        Metric name, e.g. ``"http_req_duration"``.
    value : float
        Observed value.
    timestamp : int
        Monotonic nanoseconds via ``time.monotonic_ns()``.
    tags : dict[str, str]
        Low-cardinality indexed dimensions.

    >>> s = Sample("http_reqs", 1.0, 0, {"method": "GET"})
    >>> s.metric
    'http_reqs'
    >>> s.tags["method"]
    'GET'
    """

    metric: str
    value: float
    timestamp: int
    tags: dict[str, str]


def make_sample(
    metric: str,
    value: float,
    tags: dict[str, str] | None = None,
) -> Sample:
    """Create a sample with the current monotonic timestamp.

    Parameters
    ----------
    metric : str
        Metric name.
    value : float
        Observed value.
    tags : dict[str, str] | None
        Optional tags. Defaults to an empty dict.

    Returns
    -------
    Sample
        A new sample with ``timestamp`` set to ``time.monotonic_ns()``.

    >>> s = make_sample("iterations", 1.0)
    >>> s.metric
    'iterations'
    >>> s.value
    1.0
    >>> isinstance(s.timestamp, int)
    True
    >>> s.tags
    {}
    """
    return Sample(
        metric=metric,
        value=value,
        timestamp=time.monotonic_ns(),
        tags=tags if tags is not None else {},
    )
