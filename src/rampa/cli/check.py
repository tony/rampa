"""Check subcommand for rampa CLI.

>>> import rampa.cli.check
"""

from __future__ import annotations

import argparse
import sys

from rampa.cli._colors import build_description

CHECK_DESCRIPTION = build_description(
    "Validate a test script without running it.",
    (
        (
            None,
            [
                "rampa check load_test.py",
            ],
        ),
    ),
)


def create_check_subparser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the check subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The check subparser to configure.

    Examples
    --------
    >>> import argparse
    >>> p = argparse.ArgumentParser()
    >>> create_check_subparser(p)
    """
    parser.add_argument("script", help="path to the test script")


def command_check(args: argparse.Namespace) -> None:
    """Execute the check command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments with script.

    Examples
    --------
    >>> from rampa.cli.check import command_check
    >>> command_check.__name__
    'command_check'
    """
    from rampa.loader import load_test

    try:
        plan = load_test(args.script)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    from rampa.executors import create_executor

    print(f"scenarios: {len(plan.scenarios)} found")
    for name, (cfg, _fn) in plan.scenarios.items():
        parts = [f"  - {name} ({cfg.executor}"]
        if cfg.vus is not None:
            parts.append(f", {cfg.vus} VUs")
        if cfg.duration is not None:
            secs = cfg.duration.total_seconds()
            if secs >= 1:
                parts.append(f", {secs:.0f}s")
            else:
                parts.append(f", {secs * 1000:.0f}ms")
        if cfg.iterations is not None:
            parts.append(f", {cfg.iterations} iterations")
        parts.append(")")
        print("".join(parts))

        try:
            create_executor(cfg)
        except ValueError as e:
            print(f"    error: {e}", file=sys.stderr)
            sys.exit(1)

    if plan.config.thresholds:
        print(f"thresholds: {len(plan.config.thresholds)} configured")
    print(f"setup: {'yes' if plan.setup_fn else 'no'}")
    print(f"teardown: {'yes' if plan.teardown_fn else 'no'}")
    print("status: valid")
