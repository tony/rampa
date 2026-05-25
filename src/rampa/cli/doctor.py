"""Doctor subcommand for rampa CLI.

>>> import rampa.cli.doctor
"""

from __future__ import annotations

import argparse
import platform

from rampa.cli._colors import build_description

DOCTOR_DESCRIPTION = build_description(
    "Check the runtime environment for rampa.",
    (
        (
            None,
            [
                "rampa doctor",
            ],
        ),
    ),
)


def create_doctor_subparser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the doctor subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The doctor subparser to configure.

    Examples
    --------
    >>> import argparse
    >>> p = argparse.ArgumentParser()
    >>> create_doctor_subparser(p)
    """


def command_doctor(args: argparse.Namespace) -> None:
    """Execute the doctor command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments (no specific args for doctor).

    Examples
    --------
    >>> from rampa.cli.doctor import command_doctor
    >>> command_doctor.__name__
    'command_doctor'
    """
    import importlib.metadata

    print(f"python: {platform.python_version()}")
    print(f"rampa: {importlib.metadata.version('rampa')}")
    print(f"platform: {platform.system().lower()} ({platform.machine()})")

    import aiohttp

    print(f"aiohttp: {aiohttp.__version__}")

    for extra_name, module_name in [
        ("uvloop", "uvloop"),
        ("textual", "textual"),
        ("fastmcp", "fastmcp"),
    ]:
        try:
            mod = __import__(module_name)
            ver = getattr(mod, "__version__", "installed")
            print(f"{extra_name}: {ver}")
        except ImportError:
            print(f"{extra_name}: not installed")
