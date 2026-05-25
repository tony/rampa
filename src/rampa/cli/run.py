"""Run subcommand for rampa CLI.

>>> import rampa.cli.run
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rampa.cli._colors import build_description
from rampa.errors import ExitCode

RUN_DESCRIPTION = build_description(
    "Execute a load test script.",
    (
        (
            None,
            [
                "rampa run load_test.py",
                "rampa run load_test.py --vus 20 --duration 1m",
                "rampa run load_test.py --scenario smoke",
            ],
        ),
        (
            "output",
            [
                "rampa run load_test.py --out results.json --quiet",
                "rampa run load_test.py --event-log events.jsonl",
            ],
        ),
    ),
)


def create_run_subparser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the run subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The run subparser to configure.

    Examples
    --------
    >>> import argparse
    >>> p = argparse.ArgumentParser()
    >>> create_run_subparser(p)
    """
    parser.add_argument("script", help="path to the test script")
    parser.add_argument("--vus", type=int, default=None, help="override VU count")
    parser.add_argument(
        "--duration",
        type=str,
        default=None,
        help="override duration (e.g. `30s`, `1m`)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="run a specific scenario only",
    )
    parser.add_argument(
        "--out",
        dest="json_output",
        type=str,
        default=None,
        help="JSON output file path",
    )
    parser.add_argument(
        "--event-log",
        type=str,
        default=None,
        help="JSONL event log file path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="suppress console summary",
    )


def command_run(args: argparse.Namespace) -> None:
    """Execute the run command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments with script, vus, duration, scenario, json_output,
        event_log, quiet.

    Examples
    --------
    >>> from rampa.cli.run import command_run
    >>> command_run.__name__
    'command_run'
    """
    from rampa.loader import load_test

    try:
        plan = load_test(args.script)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(ExitCode.INVALID_CONFIG)

    if args.vus is not None:
        for cfg, _fn in plan.scenarios.values():
            cfg.vus = args.vus

    if args.duration is not None:
        from rampa.config import parse_duration

        td = parse_duration(args.duration)
        for cfg, _fn in plan.scenarios.values():
            cfg.duration = td

    if args.scenario is not None:
        if args.scenario not in plan.scenarios:
            print(f"Error: scenario {args.scenario!r} not found", file=sys.stderr)
            sys.exit(ExitCode.INVALID_CONFIG)
        plan.scenarios = {args.scenario: plan.scenarios[args.scenario]}

    from rampa.runner import run_test, status_to_exit_code

    result = asyncio.run(
        run_test(
            plan,
            json_output_path=args.json_output,
            quiet=args.quiet,
            event_log_path=args.event_log,
        ),
    )
    sys.exit(status_to_exit_code(result.status))
