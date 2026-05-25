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
        "--log-level",
        "--color",
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

    Python 3.14+ sets ``self._theme`` on ``HelpFormatter`` instances
    via ``_colorize.get_theme().argparse``.
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

    When ``_theme`` is ``None`` (older Python or ``NO_COLOR`` set),
    ``_fill_text`` falls through to the base class unchanged.

    Examples
    --------
    >>> formatter = RampaHelpFormatter("rampa")
    >>> formatter  # doctest: +ELLIPSIS
    <...RampaHelpFormatter object at ...>
    """

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        """Fill text, colorizing example sections if theme is available.

        Examples
        --------
        >>> formatter = RampaHelpFormatter("test")
        >>> formatter._fill_text("hello", 80, "")
        'hello'
        """
        theme = t.cast("_HelpTheme | None", getattr(self, "_theme", None))
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
                formatted_content = stripped_line

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
        >>> from rampa.cli._formatter import HelpTheme
        >>> formatter = RampaHelpFormatter("test")
        >>> theme = HelpTheme.from_colors(None)
        >>> result = formatter._colorize_example_line(
        ...     "rampa run", theme=theme, expect_value=False
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


class HelpTheme(t.NamedTuple):
    """Theme colors for help output.

    Examples
    --------
    >>> theme = HelpTheme.from_colors(None)
    >>> theme.reset
    ''
    """

    prog: str
    action: str
    long_option: str
    short_option: str
    label: str
    heading: str
    reset: str

    @classmethod
    def from_colors(cls, colors: t.Any) -> HelpTheme:
        """Create theme from Colors instance.

        Parameters
        ----------
        colors : Colors | None
            Colors instance, or None for no colors.

        Returns
        -------
        HelpTheme
            Theme with ANSI codes if enabled, empty strings otherwise.

        Examples
        --------
        >>> HelpTheme.from_colors(None).reset
        ''
        """
        if colors is None or not colors._enabled:
            return cls(
                prog="",
                action="",
                long_option="",
                short_option="",
                label="",
                heading="",
                reset="",
            )

        from rampa.cli._colors import style

        return cls(
            prog=style("", fg="magenta", bold=True).removesuffix("\033[0m"),
            action=style("", fg="cyan").removesuffix("\033[0m"),
            long_option=style("", fg="green").removesuffix("\033[0m"),
            short_option=style("", fg="green").removesuffix("\033[0m"),
            label=style("", fg="yellow").removesuffix("\033[0m"),
            heading=style("", fg="blue").removesuffix("\033[0m"),
            reset="\033[0m",
        )


def create_themed_formatter(
    colors: t.Any | None = None,
) -> type[RampaHelpFormatter]:
    """Create a help formatter class with theme bound.

    Parameters
    ----------
    colors : Colors | None
        Colors instance. If None, uses ColorMode.AUTO.

    Returns
    -------
    type[RampaHelpFormatter]
        Formatter class with theme bound.

    Examples
    --------
    >>> from rampa.cli._colors import ColorMode, Colors
    >>> formatter_cls = create_themed_formatter(Colors(ColorMode.NEVER))
    >>> formatter = formatter_cls("test")
    >>> formatter._theme is None
    True
    """
    from rampa.cli._colors import ColorMode, Colors

    if colors is None:
        colors = Colors(ColorMode.AUTO)

    theme = HelpTheme.from_colors(colors) if colors._enabled else None

    class ThemedRampaHelpFormatter(RampaHelpFormatter):
        """RampaHelpFormatter with theme pre-configured."""

        def __init__(self, prog: str, **kwargs: t.Any) -> None:
            super().__init__(prog, **kwargs)
            self._theme = theme

    return ThemedRampaHelpFormatter
