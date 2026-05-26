"""CLI entry point for ``python -m rampa.ci.compare``.

>>> import rampa.ci.__main__
"""

from __future__ import annotations

import argparse
import sys

from rampa.ci.compare import compare_results, format_json, format_markdown, format_text


def main(argv: list[str] | None = None) -> None:
    """Compare two rampa JSON result files.

    >>> main.__name__
    'main'
    """
    parser = argparse.ArgumentParser(
        prog="python -m rampa.ci.compare",
        description="Compare two rampa JSON result files.",
    )
    parser.add_argument("--baseline", required=True, help="baseline JSON file")
    parser.add_argument("--current", required=True, help="current JSON file")
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
    )
    args = parser.parse_args(argv)

    deltas = compare_results(args.baseline, args.current)

    if args.format == "markdown":
        sys.stdout.write(format_markdown(deltas) + "\n")
    elif args.format == "json":
        sys.stdout.write(format_json(deltas) + "\n")
    else:
        sys.stdout.write(format_text(deltas) + "\n")


if __name__ == "__main__":
    main()
