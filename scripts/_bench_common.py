"""Shared utilities for rampa benchmark scripts.

Provides environment metadata and env-var helpers used across all
benchmark scripts.

>>> info = build_env_info()
>>> "python_version" in info
True
>>> "rust_extension_present" in info
True
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import typing as t


def parse_env_int(name: str, default: int) -> int:
    """Parse an integer from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int
        Default value if not set.

    Returns
    -------
    int
        Parsed value.

    >>> parse_env_int("_BENCH_COMMON_MISSING", 42)
    42
    """
    return int(os.environ.get(name, str(default)))


def parse_env_float(name: str, default: float) -> float:
    """Parse a float from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : float
        Default value if not set.

    Returns
    -------
    float
        Parsed value.

    >>> parse_env_float("_BENCH_COMMON_MISSING", 3.14)
    3.14
    """
    return float(os.environ.get(name, str(default)))


def build_env_info() -> dict[str, t.Any]:
    """Build environment metadata for benchmark output.

    Returns
    -------
    dict[str, Any]
        Dictionary with ``python_version``, ``python_implementation``,
        ``platform``, ``rampa_commit``, ``rust_extension_present``, and
        ``free_threaded`` keys.

    >>> info = build_env_info()
    >>> isinstance(info["python_version"], str)
    True
    >>> isinstance(info["rust_extension_present"], bool)
    True
    """
    commit = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except FileNotFoundError:
        pass

    rust_present = False
    try:
        import rampa._core  # noqa: F401

        rust_present = True
    except ImportError:
        pass

    free_threaded = False
    if hasattr(sys, "_is_gil_enabled"):
        free_threaded = not sys._is_gil_enabled()  # type: ignore[attr-defined]

    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "rampa_commit": commit,
        "rust_extension_present": rust_present,
        "free_threaded": free_threaded,
    }
