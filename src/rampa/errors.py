"""Structured failure taxonomy for rampa.

Every failure mode maps to a distinct exit code so CI systems can distinguish
"test failed performance criteria" from "test script crashed."

>>> import rampa.errors
"""

from __future__ import annotations

import enum


class ExitCode(enum.IntEnum):
    """Process exit codes for each failure category.

    >>> ExitCode.OK
    <ExitCode.OK: 0>
    >>> int(ExitCode.THRESHOLD_FAILURE)
    1
    >>> ExitCode.ABORTED.value
    4
    """

    OK = 0
    THRESHOLD_FAILURE = 1
    ITERATION_EXCEPTION = 2
    INVALID_CONFIG = 3
    ABORTED = 4
    SETUP_FAILURE = 5
    OUTPUT_FAILURE = 6
    TEARDOWN_FAILURE = 7


class RampaError(Exception):
    """Base exception for all rampa errors.

    Parameters
    ----------
    message : str
        Human-readable error description.
    exit_code : ExitCode
        Process exit code for this failure category.

    >>> err = RampaError("something broke", ExitCode.ABORTED)
    >>> err.exit_code
    <ExitCode.ABORTED: 4>
    >>> str(err)
    'something broke'
    """

    def __init__(self, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ThresholdError(RampaError):
    """One or more thresholds breached.

    >>> err = ThresholdError("p(95) > 500ms")
    >>> err.exit_code
    <ExitCode.THRESHOLD_FAILURE: 1>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.THRESHOLD_FAILURE)


class ConfigError(RampaError):
    """Scenario or option validation failed.

    >>> err = ConfigError("invalid executor type")
    >>> err.exit_code
    <ExitCode.INVALID_CONFIG: 3>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.INVALID_CONFIG)


class SetupError(RampaError):
    """Setup function raised an exception.

    >>> err = SetupError("setup() failed")
    >>> err.exit_code
    <ExitCode.SETUP_FAILURE: 5>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.SETUP_FAILURE)


class AbortError(RampaError):
    """Test run was aborted by user or abort-on-fail threshold.

    >>> err = AbortError("SIGINT received")
    >>> err.exit_code
    <ExitCode.ABORTED: 4>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.ABORTED)


class OutputError(RampaError):
    """Output plugin failed to start or flush.

    >>> err = OutputError("JSON write failed")
    >>> err.exit_code
    <ExitCode.OUTPUT_FAILURE: 6>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.OUTPUT_FAILURE)


class TeardownError(RampaError):
    """Teardown function raised an exception.

    >>> err = TeardownError("teardown() failed")
    >>> err.exit_code
    <ExitCode.TEARDOWN_FAILURE: 7>
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, ExitCode.TEARDOWN_FAILURE)
