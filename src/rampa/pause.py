"""Pause/resume controller for mid-test execution control.

The controller uses an asyncio.Event as the gate: set means running,
clear means paused. Executors call ``wait_if_paused()`` before each
iteration — the await returns immediately when not paused (zero overhead).

>>> import rampa.pause
"""

from __future__ import annotations

import asyncio
import time


class PauseController:
    """Controls pause/resume state for a running test.

    The paused duration is tracked so that the MetricEngine can adjust
    elapsed time calculations.

    Examples
    --------
    >>> pc = PauseController()
    >>> pc.is_paused
    False
    >>> pc.total_paused_seconds
    0.0
    """

    def __init__(self) -> None:
        self._gate = asyncio.Event()
        self._gate.set()
        self._pause_start: float | None = None
        self._total_paused: float = 0.0

    @property
    def is_paused(self) -> bool:
        """Return whether execution is currently paused.

        >>> PauseController().is_paused
        False
        """
        return not self._gate.is_set()

    @property
    def total_paused_seconds(self) -> float:
        """Return accumulated pause duration in seconds.

        Includes the current pause if one is active.

        >>> PauseController().total_paused_seconds
        0.0
        """
        total = self._total_paused
        if self._pause_start is not None:
            total += time.monotonic() - self._pause_start
        return total

    def pause(self) -> None:
        """Pause execution.

        Idempotent — calling while already paused is a no-op.

        >>> pc = PauseController()
        >>> pc.pause()
        >>> pc.is_paused
        True
        """
        if not self.is_paused:
            self._pause_start = time.monotonic()
            self._gate.clear()

    def resume(self) -> None:
        """Resume execution.

        Idempotent — calling while already running is a no-op.

        >>> pc = PauseController()
        >>> pc.pause()
        >>> pc.resume()
        >>> pc.is_paused
        False
        """
        if self.is_paused and self._pause_start is not None:
            self._total_paused += time.monotonic() - self._pause_start
            self._pause_start = None
        self._gate.set()

    async def wait_if_paused(self) -> None:
        """Block until execution resumes.

        Returns immediately when not paused. Executors call this before
        each iteration.

        >>> import asyncio
        >>> pc = PauseController()
        >>> asyncio.run(pc.wait_if_paused())
        """
        await self._gate.wait()
