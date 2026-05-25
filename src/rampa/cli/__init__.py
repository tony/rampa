"""Argparse-based CLI entry point for rampa.

>>> import rampa.cli
"""

from __future__ import annotations

import argparse
import sys
import typing as t

from rampa.cli._colors import build_description
from rampa.cli._formatter import RampaHelpFormatter
from rampa.cli.check import CHECK_DESCRIPTION, command_check, create_check_subparser
from rampa.cli.doctor import DOCTOR_DESCRIPTION, command_doctor, create_doctor_subparser
from rampa.cli.run import RUN_DESCRIPTION, command_run, create_run_subparser

CLI_DESCRIPTION = build_description(
    "Rampa — Python load testing framework.",
    (
        (
            "run",
            [
                "rampa run load_test.py",
                "rampa run load_test.py --vus 20 --duration 1m",
                "rampa run load_test.py --scenario smoke",
                "rampa run load_test.py --out results.json --quiet",
            ],
        ),
        (
            "check",
            [
                "rampa check load_test.py",
            ],
        ),
        (
            "doctor",
            [
                "rampa doctor",
            ],
        ),
    ),
)


def create_parser() -> argparse.ArgumentParser:
    """Build the rampa CLI argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with run, check, and doctor subcommands.

    Examples
    --------
    >>> parser = create_parser()
    >>> parser.prog
    'rampa'
    """
    from importlib.metadata import version

    parser = argparse.ArgumentParser(
        prog="rampa",
        formatter_class=RampaHelpFormatter,
        description=CLI_DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {version('rampa')}",
    )

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="run a load test script",
        formatter_class=RampaHelpFormatter,
        description=RUN_DESCRIPTION,
    )
    create_run_subparser(run_parser)

    check_parser = subparsers.add_parser(
        "check",
        help="validate a test script without running it",
        formatter_class=RampaHelpFormatter,
        description=CHECK_DESCRIPTION,
    )
    create_check_subparser(check_parser)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="check the runtime environment",
        formatter_class=RampaHelpFormatter,
        description=DOCTOR_DESCRIPTION,
    )
    create_doctor_subparser(doctor_parser)

    return parser


def build_docs_parser() -> argparse.ArgumentParser:
    """Return the parser for sphinx-autodoc-argparse.

    Returns
    -------
    argparse.ArgumentParser
        The root parser.

    Examples
    --------
    >>> parser = build_docs_parser()
    >>> parser.prog
    'rampa'
    """
    return create_parser()


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for rampa.

    Parameters
    ----------
    argv : list[str] | None
        Command-line arguments. None uses sys.argv.

    Examples
    --------
    >>> import rampa.cli
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        command_run(args)
    elif args.command == "check":
        command_check(args)
    elif args.command == "doctor":
        command_doctor(args)
