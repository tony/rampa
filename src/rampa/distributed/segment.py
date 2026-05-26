"""Execution segments for deterministic work partitioning.

Segments divide VUs, iterations, and arrival rates across workers
without central assignment. Each worker independently computes its
share from its index and the total worker count.

>>> import rampa.distributed.segment
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionSegment:
    """Integer-range partition for deterministic VU/iteration assignment.

    For N workers running K total VUs, worker i gets VUs
    ``[i*K//N, (i+1)*K//N)``. The same logic applies to iterations
    and arrival rates.

    Parameters
    ----------
    index : int
        Zero-based worker index.
    total : int
        Total number of workers in the cluster.

    Examples
    --------
    >>> seg = ExecutionSegment(index=0, total=3)
    >>> seg.vu_range(10)
    range(0, 3)
    >>> seg = ExecutionSegment(index=1, total=3)
    >>> seg.vu_range(10)
    range(3, 6)
    >>> seg = ExecutionSegment(index=2, total=3)
    >>> seg.vu_range(10)
    range(6, 10)
    """

    index: int
    total: int

    def __post_init__(self) -> None:
        """Validate segment parameters.

        >>> ExecutionSegment(index=0, total=1)
        ExecutionSegment(index=0, total=1)
        """
        if self.total < 1:
            msg = f"total must be >= 1, got {self.total}"
            raise ValueError(msg)
        if not (0 <= self.index < self.total):
            msg = f"index must be in [0, {self.total}), got {self.index}"
            raise ValueError(msg)

    def vu_range(self, total_vus: int) -> range:
        """Return the VU IDs this segment owns.

        Parameters
        ----------
        total_vus : int
            Total VU count across all segments.

        Returns
        -------
        range
            Zero-based VU ID range for this segment.

        >>> ExecutionSegment(0, 2).vu_range(10)
        range(0, 5)
        >>> ExecutionSegment(1, 2).vu_range(10)
        range(5, 10)
        """
        start = self.index * total_vus // self.total
        end = (self.index + 1) * total_vus // self.total
        return range(start, end)

    def iteration_range(self, total_iterations: int) -> range:
        """Return the iteration IDs this segment owns.

        Parameters
        ----------
        total_iterations : int
            Total iteration count across all segments.

        Returns
        -------
        range
            Zero-based iteration ID range.

        >>> ExecutionSegment(0, 4).iteration_range(100)
        range(0, 25)
        """
        start = self.index * total_iterations // self.total
        end = (self.index + 1) * total_iterations // self.total
        return range(start, end)

    def scale_rate(self, total_rate: float) -> float:
        """Return this segment's share of a total arrival rate.

        Parameters
        ----------
        total_rate : float
            Desired total arrival rate (e.g. requests/sec).

        Returns
        -------
        float
            This segment's proportional rate.

        >>> ExecutionSegment(0, 4).scale_rate(100.0)
        25.0
        >>> ExecutionSegment(0, 3).scale_rate(100.0)  # doctest: +ELLIPSIS
        33.3...
        """
        segment_vus = len(self.vu_range(self.total))
        return total_rate * segment_vus / self.total

    @property
    def fraction(self) -> float:
        """Return the fraction of total work this segment handles.

        >>> ExecutionSegment(0, 4).fraction
        0.25
        """
        return 1.0 / self.total
