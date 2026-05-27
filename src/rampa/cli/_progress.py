"""Single-line progress display for rampa run.

Uses carriage return updates for a compact status line during test
execution. No external dependencies beyond the standard library.

>>> import rampa.cli._progress
"""

from __future__ import annotations

import sys
import typing as t

if t.TYPE_CHECKING:
    from rampa.metrics import MetricSnapshot


def format_progress_line(snapshot: MetricSnapshot) -> str:
    """Format a single-line progress string from a metric snapshot.

    Parameters
    ----------
    snapshot : MetricSnapshot
        Current metric aggregation.

    Returns
    -------
    str
        Compact progress line.

    >>> from rampa.metrics import MetricSnapshot
    >>> snap = MetricSnapshot(
    ...     timestamp=0,
    ...     duration=10.0,
    ...     values={
    ...         "vus": {"value": 5.0},
    ...         "iterations": {"count": 100.0, "rate": 10.0},
    ...         "http_req_duration": {"p(95)": 45.2},
    ...     },
    ... )
    >>> line = format_progress_line(snap)
    >>> "VUs: 5" in line
    True
    >>> "10.0/s" in line
    True
    """

    def _get(metric: str, stat: str) -> float:
        return snapshot.values.get(metric, {}).get(stat, 0.0)

    vus = int(_get("vus", "value"))
    iters = int(_get("iterations", "count"))
    rate = _get("iterations", "rate")
    p95 = _get("http_req_duration", "p(95)")
    dur = snapshot.duration

    return f" {dur:.0f}s | VUs: {vus} | Reqs: {iters} ({rate:.1f}/s) | p95: {p95:.1f}ms"


def write_progress(snapshot: MetricSnapshot, stream: t.TextIO | None = None) -> None:
    """Write a carriage-return progress line to the stream.

    Parameters
    ----------
    snapshot : MetricSnapshot
        Current metric aggregation.
    stream : TextIO | None
        Output stream. Defaults to stderr.
    """
    out = stream or sys.stderr
    line = format_progress_line(snapshot)
    out.write(f"\r{line}")
    out.flush()


def clear_progress(stream: t.TextIO | None = None) -> None:
    """Clear the progress line.

    Parameters
    ----------
    stream : TextIO | None
        Output stream. Defaults to stderr.
    """
    out = stream or sys.stderr
    out.write("\r" + " " * 80 + "\r")
    out.flush()
