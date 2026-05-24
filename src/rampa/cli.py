"""Click-based CLI entry point for rampa.

>>> import rampa.cli
"""

from __future__ import annotations

import asyncio
import platform
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

    from rampa.runner import status_to_exit_code

    result = asyncio.run(
        run_test(plan, json_output_path=json_output, quiet=quiet),
    )
    sys.exit(status_to_exit_code(result.status))


@main.command()
@click.argument("script", type=click.Path(exists=True))
def check(script: str) -> None:
    """Validate a test script without running it.

    Loads the script, discovers scenarios, validates executor
    configurations, and prints a summary.
    """
    try:
        plan = load_test(script)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    from rampa.executors import create_executor

    click.echo(f"scenarios: {len(plan.scenarios)} found")
    for name, (cfg, _fn) in plan.scenarios.items():
        parts = [f"  - {name} ({cfg.executor}"]
        if cfg.vus is not None:
            parts.append(f", {cfg.vus} VUs")
        if cfg.duration is not None:
            parts.append(f", {cfg.duration.total_seconds():.0f}s")
        if cfg.iterations is not None:
            parts.append(f", {cfg.iterations} iterations")
        parts.append(")")
        click.echo("".join(parts))

        try:
            create_executor(cfg)
        except ValueError as e:
            click.echo(f"    error: {e}", err=True)
            sys.exit(1)

    if plan.config.thresholds:
        click.echo(f"thresholds: {len(plan.config.thresholds)} configured")
    click.echo(f"setup: {'yes' if plan.setup_fn else 'no'}")
    click.echo(f"teardown: {'yes' if plan.teardown_fn else 'no'}")
    click.echo("status: valid")


@main.command()
def doctor() -> None:
    """Check the runtime environment for rampa.

    Reports Python version, rampa version, installed dependencies,
    and optional extras availability.
    """
    from importlib.metadata import version

    click.echo(f"python: {platform.python_version()}")
    click.echo(f"rampa: {version('rampa')}")
    click.echo(f"platform: {platform.system().lower()} ({platform.machine()})")

    import aiohttp

    click.echo(f"aiohttp: {aiohttp.__version__}")

    for extra_name, module_name in [
        ("uvloop", "uvloop"),
        ("textual", "textual"),
        ("fastmcp", "fastmcp"),
    ]:
        try:
            mod = __import__(module_name)
            ver = getattr(mod, "__version__", "installed")
            click.echo(f"{extra_name}: {ver}")
        except ImportError:
            click.echo(f"{extra_name}: not installed")
