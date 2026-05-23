"""Click-based CLI entry point for rampa.

>>> import rampa.cli
"""

from __future__ import annotations

import asyncio
import sys

import click

from rampa.errors import ExitCode
from rampa.loader import load_test
from rampa.runner import run_test


@click.group()
@click.version_option(package_name="rampa")
def main() -> None:
    """Rampa — Python load testing framework."""


@main.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--vus", type=int, default=None, help="Number of virtual users.")
@click.option("--duration", type=str, default=None, help="Test duration (e.g. 30s, 1m).")
@click.option("--scenario", type=str, default=None, help="Run a specific scenario.")
@click.option("--out", "json_output", type=str, default=None, help="JSON output file path.")
@click.option("--quiet", is_flag=True, default=False, help="Suppress console summary.")
def run(
    script: str,
    vus: int | None,
    duration: str | None,
    scenario: str | None,
    json_output: str | None,
    quiet: bool,
) -> None:
    """Run a load test script.

    SCRIPT is the path to a Python file containing @scenario-decorated
    async functions.
    """
    try:
        plan = load_test(script)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(ExitCode.INVALID_CONFIG)

    if vus is not None:
        for cfg, _fn in plan.scenarios.values():
            cfg.vus = vus

    if duration is not None:
        from rampa.config import parse_duration

        td = parse_duration(duration)
        for cfg, _fn in plan.scenarios.values():
            cfg.duration = td

    if scenario is not None:
        if scenario not in plan.scenarios:
            click.echo(f"Error: scenario {scenario!r} not found", err=True)
            sys.exit(ExitCode.INVALID_CONFIG)
        plan.scenarios = {
            scenario: plan.scenarios[scenario],
        }

    result = asyncio.run(
        run_test(plan, json_output_path=json_output, quiet=quiet),
    )
    sys.exit(result.exit_code)
