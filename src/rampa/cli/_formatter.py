"""Custom help formatter for rampa CLI with colorized examples.

Extends Python 3.14+ native argparse colorization to also highlight
example command blocks in description text.

>>> from rampa.cli._formatter import RampaHelpFormatter
>>> RampaHelpFormatter  # doctest: +ELLIPSIS
<class '...RampaHelpFormatter'>
"""

from __future__ import annotations

import argparse
import re
import typing as t

OPTIONS_EXPECTING_VALUE = frozenset(
    {
        "--vus",
        "--duration",
        "--scenario",
        "--out",
        "--event-log",
    }
)

OPTIONS_FLAG_ONLY = frozenset(
    {
        "-h",
        "--help",
        "-V",
        "--version",
        "--quiet",
    }
)


class _HelpTheme(t.Protocol):
    """Protocol for the argparse color theme.

    Python 3.14+ exposes ``_colorize.get_theme().argparse`` as ``_theme`` on
    ``HelpFormatter`` instances (an attribute on 3.14, a read-only property on
    3.15).
    """

    heading: str
    reset: str
    label: str
    long_option: str
    short_option: str
    prog: str
    action: str


class RampaHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Extend Python 3.14+ native help colors with example-block colorization.

    Examples follow argparse's own theme, so they share its on/off decision
    (``NO_COLOR``, ``FORCE_COLOR``, the output stream) and palette with the
    usage line. The formatter only reads ``_theme``: argparse owns that name.

    Examples
    --------
    >>> formatter = RampaHelpFormatter("rampa")
    >>> formatter  # doctest: +ELLIPSIS
    <...RampaHelpFormatter object at ...>
    """

    def _example_theme(self) -> _HelpTheme | None:
        """Return argparse's help theme, the palette for example sections.

        Examples
        --------
        >>> RampaHelpFormatter("rampa")._example_theme() is not None
        True
        """
        return t.cast("_HelpTheme | None", getattr(self, "_theme", None))

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        """Fill text, colorizing example sections if theme is available.

        Examples
        --------
        >>> formatter = RampaHelpFormatter("test")
        >>> formatter._fill_text("hello", 80, "")
        'hello'
        """
        theme = self._example_theme()
        if not text or theme is None:
            return super()._fill_text(text, width, indent)

        lines = text.splitlines(keepends=True)
        formatted_lines: list[str] = []
        in_examples_block = False
        expect_value = False

        for line in lines:
            if line.strip() == "":
                in_examples_block = False
                expect_value = False
                formatted_lines.append(f"{indent}{line}")
                continue

            has_newline = line.endswith("\n")
            stripped_line = line.rstrip("\n")
            leading_length = len(stripped_line) - len(stripped_line.lstrip(" "))
            leading = stripped_line[:leading_length]
            content = stripped_line[leading_length:]
            content_lower = content.lower()
            is_section_heading = (
                content_lower.endswith("examples:") and content_lower != "examples:"
            )

            if is_section_heading or content_lower == "examples:":
                formatted_content = f"{theme.heading}{content}{theme.reset}"
                in_examples_block = True
                expect_value = False
            elif in_examples_block:
                colored_content = self._colorize_example_line(
                    content,
                    theme=theme,
                    expect_value=expect_value,
                )
                expect_value = colored_content.expect_value
                formatted_content = colored_content.text
            else:
                formatted_content = content

            newline = "\n" if has_newline else ""
            formatted_lines.append(f"{indent}{leading}{formatted_content}{newline}")

        return "".join(formatted_lines)

    class _ColorizedLine(t.NamedTuple):
        """Result of colorizing an example line."""

        text: str
        expect_value: bool

    def _colorize_example_line(
        self,
        content: str,
        *,
        theme: _HelpTheme,
        expect_value: bool,
    ) -> _ColorizedLine:
        """Colorize a single example command line.

        Parameters
        ----------
        content : str
            Line content.
        theme : _HelpTheme
            Theme with color attributes.
        expect_value : bool
            Whether the previous token expects a value.

        Returns
        -------
        _ColorizedLine
            Colorized text and updated expect_value state.

        Examples
        --------
        With argparse's theme for uncolored output, the line is unchanged:

        >>> formatter = RampaHelpFormatter("test")
        >>> result = formatter._colorize_example_line(
        ...     "rampa run", theme=formatter._example_theme(), expect_value=False
        ... )
        >>> result.text
        'rampa run'
        """
        parts: list[str] = []
        expecting_value = expect_value
        first_token = True
        colored_subcommand = False

        for match in re.finditer(r"\s+|\S+", content):
            token = match.group()
            if token.isspace():
                parts.append(token)
                continue

            if expecting_value:
                color = theme.label
                expecting_value = False
            elif token.startswith("--"):
                color = theme.long_option
                expecting_value = (
                    token not in OPTIONS_FLAG_ONLY and token in OPTIONS_EXPECTING_VALUE
                )
            elif token.startswith("-"):
                color = theme.short_option
                expecting_value = (
                    token not in OPTIONS_FLAG_ONLY and token in OPTIONS_EXPECTING_VALUE
                )
            elif first_token:
                color = theme.prog
            elif not colored_subcommand:
                color = theme.action
                colored_subcommand = True
            else:
                color = None

            first_token = False

            if color:
                parts.append(f"{color}{token}{theme.reset}")
            else:
                parts.append(token)

        return self._ColorizedLine(text="".join(parts), expect_value=expecting_value)
