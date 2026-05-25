"""Color output utilities for rampa CLI.

>>> from rampa.cli._colors import ColorMode, Colors
>>> Colors(ColorMode.NEVER).success("ok")
'ok'
"""

from __future__ import annotations

import enum
import os
import re
import sys
import textwrap
import typing as t

if t.TYPE_CHECKING:
    type CLIColour = int | tuple[int, int, int] | str


class ColorMode(enum.Enum):
    """Color output modes.

    >>> ColorMode.AUTO.value
    'auto'
    """

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class Colors:
    r"""Semantic color utilities for CLI output.

    Respects ``NO_COLOR``, ``FORCE_COLOR``, ``PYTHON_COLORS``, and TTY.

    Parameters
    ----------
    mode : ColorMode
        Color mode. Default is AUTO.

    Examples
    --------
    >>> colors = Colors(ColorMode.NEVER)
    >>> colors.success("passed")
    'passed'
    >>> colors.error("failed")
    'failed'
    """

    SUCCESS = "green"
    WARNING = "yellow"
    ERROR = "red"
    INFO = "cyan"
    HIGHLIGHT = "magenta"
    MUTED = "blue"

    def __init__(self, mode: ColorMode = ColorMode.AUTO) -> None:
        self.mode = mode
        self._enabled = self._should_enable()

    def _should_enable(self) -> bool:
        """Determine if color should be enabled.

        Returns
        -------
        bool
            True if colors should be enabled.

        Examples
        --------
        >>> Colors(ColorMode.NEVER)._should_enable()
        False
        """
        if os.environ.get("NO_COLOR"):
            return False
        if self.mode == ColorMode.NEVER:
            return False
        if self.mode == ColorMode.ALWAYS:
            return True
        if os.environ.get("FORCE_COLOR"):
            return True
        return sys.stdout.isatty()

    def _colorize(self, text: str, fg: str, bold: bool = False) -> str:
        """Apply color if enabled.

        Examples
        --------
        >>> Colors(ColorMode.NEVER)._colorize("x", "green")
        'x'
        """
        if self._enabled:
            return style(text, fg=fg, bold=bold)
        return text

    def success(self, text: str, bold: bool = False) -> str:
        """Format as success (green).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).success("ok")
        'ok'
        """
        return self._colorize(text, self.SUCCESS, bold)

    def warning(self, text: str, bold: bool = False) -> str:
        """Format as warning (yellow).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).warning("caution")
        'caution'
        """
        return self._colorize(text, self.WARNING, bold)

    def error(self, text: str, bold: bool = False) -> str:
        """Format as error (red).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).error("fail")
        'fail'
        """
        return self._colorize(text, self.ERROR, bold)

    def info(self, text: str, bold: bool = False) -> str:
        """Format as info (cyan).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).info("note")
        'note'
        """
        return self._colorize(text, self.INFO, bold)

    def highlight(self, text: str, bold: bool = True) -> str:
        """Format as highlighted (magenta).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).highlight("important")
        'important'
        """
        return self._colorize(text, self.HIGHLIGHT, bold)

    def muted(self, text: str) -> str:
        """Format as muted (blue).

        Examples
        --------
        >>> Colors(ColorMode.NEVER).muted("aside")
        'aside'
        """
        return self._colorize(text, self.MUTED, bold=False)


def get_color_mode(color_arg: str | None = None) -> ColorMode:
    """Determine color mode from argument.

    Parameters
    ----------
    color_arg : str | None
        Color mode argument (auto, always, never).

    Returns
    -------
    ColorMode
        The determined color mode.

    Examples
    --------
    >>> get_color_mode(None)
    <ColorMode.AUTO: 'auto'>
    >>> get_color_mode("never")
    <ColorMode.NEVER: 'never'>
    """
    if color_arg is None:
        return ColorMode.AUTO
    try:
        return ColorMode(color_arg.lower())
    except ValueError:
        return ColorMode.AUTO


_ANSI_RE = re.compile(r"\033\[[;?0-9]*[a-zA-Z]")

_ANSI_COLORS = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "reset": 39,
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
}
_ANSI_RESET_ALL = "\033[0m"


def strip_ansi(value: str) -> str:
    r"""Remove ANSI escape codes from a string.

    Parameters
    ----------
    value : str
        String potentially containing ANSI codes.

    Returns
    -------
    str
        String with ANSI codes removed.

    Examples
    --------
    >>> strip_ansi("\033[32mgreen\033[0m")
    'green'
    >>> strip_ansi("plain")
    'plain'
    """
    return _ANSI_RE.sub("", value)


class UnknownStyleColor(Exception):
    """Raised for unknown terminal color names.

    Examples
    --------
    >>> try:
    ...     raise UnknownStyleColor("nope")
    ... except UnknownStyleColor as e:
    ...     "nope" in str(e)
    True
    """

    def __init__(self, color: CLIColour, *args: object, **kwargs: object) -> None:
        super().__init__(f"Unknown color {color!r}", *args, **kwargs)


def _interpret_color(color: int | tuple[int, int, int] | str, offset: int = 0) -> str:
    """Convert color specification to ANSI escape code parameter.

    Parameters
    ----------
    color : int | tuple[int, int, int] | str
        Color as 256-color index, RGB tuple, or name.
    offset : int
        Offset for background colors (10 for bg).

    Returns
    -------
    str
        ANSI escape code parameters.

    Examples
    --------
    >>> _interpret_color("red")
    '31'
    >>> _interpret_color(196)
    '38;5;196'
    """
    if isinstance(color, int):
        return f"{38 + offset};5;{color:d}"
    if isinstance(color, (tuple, list)):
        r, g, b = color
        return f"{38 + offset};2;{r:d};{g:d};{b:d}"
    return str(_ANSI_COLORS[color] + offset)


def style(
    text: t.Any,
    fg: CLIColour | None = None,
    bold: bool | None = None,
    dim: bool | None = None,
    reset: bool = True,
) -> str:
    r"""Apply ANSI styling to text.

    Parameters
    ----------
    text : Any
        Text to style.
    fg : CLIColour | None
        Foreground color.
    bold : bool | None
        Apply bold.
    dim : bool | None
        Apply dim.
    reset : bool
        Append reset code. Default True.

    Returns
    -------
    str
        Styled text.

    Examples
    --------
    >>> style("hello", fg="green")  # doctest: +ELLIPSIS
    '\x1b[32m...'
    >>> "hello" in style("hello", fg="green")
    True
    """
    if not isinstance(text, str):
        text = str(text)
    bits: list[str] = []
    if fg or fg == 0:
        try:
            bits.append(f"\033[{_interpret_color(fg)}m")
        except KeyError, ValueError, TypeError:
            raise UnknownStyleColor(color=fg) from None
    if bold:
        bits.append("\033[1m")
    if dim:
        bits.append("\033[2m")
    bits.append(text)
    if reset:
        bits.append(_ANSI_RESET_ALL)
    return "".join(bits)


def build_description(
    intro: str,
    example_blocks: t.Sequence[tuple[str | None, t.Sequence[str]]],
) -> str:
    r"""Assemble help text with optional example sections.

    Parameters
    ----------
    intro : str
        The introductory description text.
    example_blocks : sequence of (heading, commands) tuples
        Each tuple contains an optional heading and a sequence of example
        commands.

    Returns
    -------
    str
        Formatted description with examples.

    Examples
    --------
    >>> build_description("My tool.", [(None, ["mytool run"])])
    'My tool.\n\nexamples:\n  mytool run'
    >>> build_description("My tool.", [("sync", ["mytool sync repo"])])
    'My tool.\n\nsync examples:\n  mytool sync repo'
    """
    sections: list[str] = []
    intro_text = textwrap.dedent(intro).strip()
    if intro_text:
        sections.append(intro_text)

    for heading, commands in example_blocks:
        if not commands:
            continue
        title = "examples:" if heading is None else f"{heading} examples:"
        lines = [title]
        lines.extend(f"  {command}" for command in commands)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
