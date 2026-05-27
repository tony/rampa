"""Rate controllers for arrival-rate executors.

Python-first implementations with optional Rust acceleration via PyO3.
The Rust accelerator uses integer nanosecond arithmetic to eliminate
cumulative float drift; the Python implementation uses equivalent logic.

When the Rust extension is available, the module-level names
``RateController`` and ``RampingRateController`` are replaced with
the native versions automatically (PEP 399-like pattern).

>>> rc = RateController(0, 1_000_000)
>>> rc.advance(3_500_000)
(3, 4000000)
>>> rc.tick
3
"""

from __future__ import annotations


class RateController:
    """Constant-rate deadline calculator.

    Uses integer nanosecond arithmetic to compute how many iterations
    are due at a given point in time.

    Parameters
    ----------
    start_ns : int
        Monotonic start time in nanoseconds.
    interval_ns : int
        Interval between ticks in nanoseconds.

    >>> rc = RateController(0, 1_000_000)
    >>> rc.advance(0)
    (0, 1000000)
    >>> rc.advance(2_500_000)
    (2, 3000000)
    >>> rc.tick
    2
    >>> rc.interval_ns
    1000000
    """

    def __init__(self, start_ns: int, interval_ns: int) -> None:
        self._start_ns = start_ns
        self._interval_ns = max(interval_ns, 1)
        self._tick = 0

    def advance(self, now_ns: int) -> tuple[int, int]:
        """Advance to the current time.

        Parameters
        ----------
        now_ns : int
            Current monotonic time in nanoseconds.

        Returns
        -------
        tuple[int, int]
            ``(due_count, next_deadline_ns)`` — how many iterations are
            due and when the next one should fire.

        >>> rc = RateController(0, 1_000_000)
        >>> rc.advance(5_000_000)
        (5, 6000000)
        """
        elapsed = max(0, now_ns - self._start_ns)
        target_tick = elapsed // self._interval_ns
        due = max(0, target_tick - self._tick)
        self._tick = target_tick
        next_ns = self._start_ns + (self._tick + 1) * self._interval_ns
        return (due, next_ns)

    @property
    def tick(self) -> int:
        """Return the current tick count.

        >>> rc = RateController(0, 100)
        >>> _ = rc.advance(350)
        >>> rc.tick
        3
        """
        return self._tick

    @property
    def interval_ns(self) -> int:
        """Return the configured interval in nanoseconds.

        >>> RateController(0, 500).interval_ns
        500
        """
        return self._interval_ns


class RampingRateController:
    """Ramping arrival-rate deadline calculator.

    Interpolates linearly between start and end rates across a stage
    duration using ``float`` arithmetic.

    Parameters
    ----------
    stage_start_ns : int
        Stage start time in nanoseconds.
    stage_duration_ns : int
        Stage duration in nanoseconds.
    start_rate : float
        Iteration rate at stage start (per time unit).
    end_rate : float
        Iteration rate at stage end (per time unit).
    time_unit_ns : float
        Time unit in nanoseconds (e.g. 1e9 for per-second rates).

    >>> rc = RampingRateController(0, 1_000_000_000, 10.0, 100.0, 1e9)
    >>> due, _ = rc.advance(500_000_000)
    >>> due > 0
    True
    >>> rc.tick > 0
    True
    """

    def __init__(
        self,
        stage_start_ns: int,
        stage_duration_ns: int,
        start_rate: float,
        end_rate: float,
        time_unit_ns: float,
    ) -> None:
        self._stage_start_ns = stage_start_ns
        self._stage_duration_ns = float(stage_duration_ns)
        self._start_rate = max(start_rate, 0.1)
        self._end_rate = max(end_rate, 0.1)
        self._time_unit_ns = max(time_unit_ns, 1.0)
        self._tick = 0
        self._accumulated_ns = 0.0

    def advance(self, now_ns: int) -> tuple[int, int]:
        """Advance to the current time.

        Parameters
        ----------
        now_ns : int
            Current monotonic time in nanoseconds.

        Returns
        -------
        tuple[int, int]
            ``(due_count, next_deadline_ns)``.

        >>> rc = RampingRateController(0, 1_000_000_000, 10.0, 10.0, 1e9)
        >>> due, _ = rc.advance(500_000_000)
        >>> due >= 0
        True
        """
        elapsed_ns = float(max(0, now_ns - self._stage_start_ns))
        due = 0

        while self._accumulated_ns <= elapsed_ns:
            progress = (
                min(self._accumulated_ns / self._stage_duration_ns, 1.0)
                if self._stage_duration_ns > 0.0
                else 1.0
            )
            rate = self._start_rate + (self._end_rate - self._start_rate) * progress
            rate = max(rate, 0.1)
            interval = self._time_unit_ns / rate
            self._accumulated_ns += interval

            if self._accumulated_ns <= elapsed_ns:
                due += 1
                self._tick += 1

        next_ns = self._stage_start_ns + int(self._accumulated_ns)
        return (due, next_ns)

    @property
    def tick(self) -> int:
        """Return the current tick count.

        >>> rc = RampingRateController(0, 1_000_000_000, 100.0, 100.0, 1e9)
        >>> _ = rc.advance(500_000_000)
        >>> rc.tick > 0
        True
        """
        return self._tick


try:
    from rampa._core import (
        RampingRateController as RampingRateController,
        RateController as RateController,
    )

    _USE_RUST_RATE: bool = True
except ImportError:
    _USE_RUST_RATE: bool = False  # type: ignore[no-redef]
