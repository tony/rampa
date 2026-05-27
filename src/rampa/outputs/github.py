"""GitHub Actions output — annotations and step summaries.

Detects the ``GITHUB_ACTIONS`` environment variable and emits
workflow commands for threshold failures and a markdown summary.

>>> import rampa.outputs.github
"""

from __future__ import annotations

import os
import sys
import typing as t

from rampa._types import Sample
from rampa.metrics import MetricSnapshot


class GitHubActionsOutput:
    """Emit GitHub Actions annotations and step summary.

    Parameters
    ----------
    summary_path : str | None
        Path to ``$GITHUB_STEP_SUMMARY``. Auto-detected from env.

    >>> import os
    >>> old = os.environ.pop("GITHUB_ACTIONS", None)
    >>> o = GitHubActionsOutput()
    >>> o._is_ci
    False
    >>> if old is not None: os.environ["GITHUB_ACTIONS"] = old
    """

    def __init__(self, summary_path: str | None = None) -> None:
        self._summary_path = summary_path or os.environ.get("GITHUB_STEP_SUMMARY", "")
        self._is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
        self._snapshot: MetricSnapshot | None = None

    async def start(self) -> None:
        """No-op."""

    async def add_samples(self, samples: list[Sample]) -> None:
        """No-op — GitHub output renders from the final snapshot."""

    async def stop(self, error: Exception | None = None) -> None:
        """No-op — rendering happens via write_summary."""

    def write_summary(
        self,
        snapshot: MetricSnapshot,
        threshold_results: list[t.Any] | None = None,
    ) -> None:
        """Write GitHub Actions annotations and step summary.

        Parameters
        ----------
        snapshot : MetricSnapshot
            Final metric aggregation.
        threshold_results : list[Any] | None
            Threshold evaluation results.
        """
        if threshold_results:
            for result in threshold_results:
                if not result.passed and self._is_ci:
                    sys.stdout.write(
                        f"::error::Threshold failed: {result.source} "
                        f"(got {result.lhs:.2f}, expected {result.rhs:.2f})\n",
                    )

        if self._summary_path:
            self._write_step_summary(snapshot, threshold_results)

    def _write_step_summary(
        self,
        snapshot: MetricSnapshot,
        threshold_results: list[t.Any] | None = None,
    ) -> None:
        lines = [
            "## rampa Results",
            "",
            f"**Duration:** {snapshot.duration:.1f}s",
            "",
        ]

        if threshold_results:
            passing = sum(1 for r in threshold_results if r.passed)
            total = len(threshold_results)
            lines.append(f"**Thresholds:** {passing}/{total} passing")
            lines.append("")
            for r in threshold_results:
                icon = ":white_check_mark:" if r.passed else ":x:"
                lines.append(f"- {icon} `{r.source}`")
            lines.append("")

        lines.extend(
            [
                "| Metric | Stat | Value |",
                "|--------|------|-------|",
            ]
        )
        for metric_name, values in sorted(snapshot.values.items()):
            for stat, val in values.items():
                if isinstance(val, float) and val == int(val) and val < 1e9:
                    lines.append(f"| {metric_name} | {stat} | {int(val)} |")
                elif isinstance(val, float):
                    lines.append(f"| {metric_name} | {stat} | {val:.2f} |")

        summary = "\n".join(lines) + "\n"
        try:
            with open(self._summary_path, "a") as f:  # noqa: PTH123
                f.write(summary)
        except OSError:
            pass
