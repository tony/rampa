"""Compare two rampa JSON result files for CI benchmarking.

Reads summary metrics from JSON output files and produces comparison
tables in text, markdown, or JSON format.

>>> import rampa.ci.compare
"""

from __future__ import annotations

import json
import pathlib
import typing as t


class MetricDelta(t.NamedTuple):
    """Comparison of a single metric stat between two runs.

    >>> d = MetricDelta("http_req_duration", "p(95)", 45.0, 52.0, 15.56)
    >>> d.pct_change
    15.56
    """

    metric: str
    stat: str
    baseline: float
    current: float
    pct_change: float


def is_regressed(delta: MetricDelta) -> bool:
    """Return True if the metric got worse (>5% increase).

    >>> is_regressed(MetricDelta("dur", "p95", 45.0, 52.0, 15.56))
    True
    >>> is_regressed(MetricDelta("dur", "p95", 45.0, 46.0, 2.2))
    False
    """
    return delta.pct_change > 5.0


def compare_results(
    baseline_path: str | pathlib.Path,
    current_path: str | pathlib.Path,
    metrics: list[str] | None = None,
) -> list[MetricDelta]:
    """Compare metrics between two JSON result files.

    Parameters
    ----------
    baseline_path : str | Path
        Path to the baseline JSON result.
    current_path : str | Path
        Path to the current JSON result.
    metrics : list[str] | None
        Metric names to compare. None compares all shared metrics.

    Returns
    -------
    list[MetricDelta]
        Per-stat deltas for each metric.

    >>> import tempfile, pathlib, json
    >>> with tempfile.TemporaryDirectory() as d:
    ...     base = pathlib.Path(d) / "base.json"
    ...     curr = pathlib.Path(d) / "curr.json"
    ...     data = {"summary": {"metrics": {"reqs": {"count": 100.0}}}}
    ...     _ = base.write_text(json.dumps(data))
    ...     data["summary"]["metrics"]["reqs"]["count"] = 120.0
    ...     _ = curr.write_text(json.dumps(data))
    ...     deltas = compare_results(base, curr)
    ...     deltas[0].pct_change
    20.0
    """
    base_data = json.loads(pathlib.Path(baseline_path).read_text())
    curr_data = json.loads(pathlib.Path(current_path).read_text())

    base_metrics = base_data.get("summary", {}).get("metrics", {})
    curr_metrics = curr_data.get("summary", {}).get("metrics", {})

    target_names = metrics or sorted(set(base_metrics) & set(curr_metrics))

    deltas: list[MetricDelta] = []
    for name in target_names:
        base_stats = base_metrics.get(name, {})
        curr_stats = curr_metrics.get(name, {})
        for stat in sorted(set(base_stats) & set(curr_stats)):
            bv = float(base_stats[stat])
            cv = float(curr_stats[stat])
            pct = ((cv - bv) / bv * 100) if bv != 0 else 0.0
            deltas.append(MetricDelta(name, stat, bv, cv, round(pct, 2)))
    return deltas


def format_text(deltas: list[MetricDelta]) -> str:
    """Format deltas as a plain text table.

    >>> deltas = [MetricDelta("dur", "p95", 45.0, 52.0, 15.56)]
    >>> "dur" in format_text(deltas)
    True
    """
    lines = [f"{'Metric':<30} {'Stat':<10} {'Base':>10} {'Current':>10} {'Change':>10}"]
    lines.append("-" * 75)
    for d in deltas:
        flag = " !" if is_regressed(d) else ""
        lines.append(
            f"{d.metric:<30} {d.stat:<10} {d.baseline:>10.2f} "
            f"{d.current:>10.2f} {d.pct_change:>+9.1f}%{flag}",
        )
    return "\n".join(lines)


def format_markdown(deltas: list[MetricDelta]) -> str:
    """Format deltas as a GitHub-flavored markdown table.

    >>> deltas = [MetricDelta("dur", "p95", 45.0, 52.0, 15.56)]
    >>> "| dur" in format_markdown(deltas)
    True
    """
    lines = [
        "## rampa Performance Report",
        "",
        "| Metric | Stat | Baseline | Current | Change |",
        "|--------|------|----------|---------|--------|",
    ]
    for d in deltas:
        flag = " :warning:" if is_regressed(d) else ""
        lines.append(
            f"| {d.metric} | {d.stat} | {d.baseline:.2f} | "
            f"{d.current:.2f} | {d.pct_change:+.1f}%{flag} |",
        )
    return "\n".join(lines)


def format_json(deltas: list[MetricDelta]) -> str:
    """Format deltas as JSON.

    >>> deltas = [MetricDelta("dur", "p95", 45.0, 52.0, 15.56)]
    >>> import json
    >>> data = json.loads(format_json(deltas))
    >>> data[0]["metric"]
    'dur'
    """
    return json.dumps(
        [
            {
                "metric": d.metric,
                "stat": d.stat,
                "baseline": d.baseline,
                "current": d.current,
                "pct_change": d.pct_change,
                "regressed": is_regressed(d),
            }
            for d in deltas
        ],
        indent=2,
    )
