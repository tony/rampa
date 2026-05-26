"""Inspect subcommand — show resolved config without running.

>>> import rampa.cli.inspect
"""

from __future__ import annotations

import argparse
import json
import sys

from rampa.cli._colors import build_description
from rampa.errors import ExitCode

INSPECT_DESCRIPTION = build_description(
    "Show the fully resolved test configuration without running.",
    (
        (
            None,
            [
                "rampa inspect load_test.py",
                "rampa inspect load_test.py --format json",
            ],
        ),
    ),
)


def create_inspect_subparser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the inspect subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The inspect subparser to configure.

    Examples
    --------
    >>> import argparse
    >>> p = argparse.ArgumentParser()
    >>> create_inspect_subparser(p)
    """
    parser.add_argument("script", help="path to the test script")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format (default: text)",
    )


def command_inspect(args: argparse.Namespace) -> None:
    """Execute the inspect command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments with script and format.

    Examples
    --------
    >>> command_inspect.__name__
    'command_inspect'
    """
    from rampa.loader import load_test

    try:
        plan = load_test(args.script)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(ExitCode.INVALID_CONFIG)

    if args.format == "json":
        _print_json(plan)
    else:
        _print_text(plan)


def _print_json(plan: object) -> None:
    from rampa.loader import TestPlan

    assert isinstance(plan, TestPlan)
    data: dict[str, object] = {
        "scenarios": {},
        "thresholds": dict(plan.config.thresholds),
        "has_setup": plan.setup_fn is not None,
        "has_teardown": plan.teardown_fn is not None,
    }
    for name, (cfg, _fn) in plan.scenarios.items():
        data["scenarios"][name] = {  # type: ignore[union-attr]
            "executor": cfg.executor,
            "vus": cfg.vus,
            "duration": str(cfg.duration) if cfg.duration else None,
            "iterations": cfg.iterations,
            "rate": cfg.rate,
            "stages": [
                {"duration": str(s.duration), "target": s.target} for s in (cfg.stages or [])
            ],
        }
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")


def _print_text(plan: object) -> None:
    from rampa.loader import TestPlan

    assert isinstance(plan, TestPlan)
    w = sys.stdout.write

    w(f"scenarios: {len(plan.scenarios)}\n")
    for name, (cfg, _fn) in plan.scenarios.items():
        w(f"\n  {name}:\n")
        w(f"    executor: {cfg.executor}\n")
        if cfg.vus is not None:
            w(f"    vus: {cfg.vus}\n")
        if cfg.duration is not None:
            w(f"    duration: {cfg.duration}\n")
        if cfg.iterations is not None:
            w(f"    iterations: {cfg.iterations}\n")
        if cfg.rate is not None:
            w(f"    rate: {cfg.rate}\n")
        if cfg.stages:
            w("    stages:\n")
            for s in cfg.stages:
                w(f"      - duration: {s.duration}, target: {s.target}\n")

    if plan.config.thresholds:
        w("\nthresholds:\n")
        for metric, exprs in plan.config.thresholds.items():
            for expr in exprs:
                w(f"  {metric}: {expr}\n")

    if plan.setup_fn is not None:
        w("\nsetup: yes\n")
    if plan.teardown_fn is not None:
        w("teardown: yes\n")
