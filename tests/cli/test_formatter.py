"""Tests for rampa CLI help formatter colorization.

>>> import tests.cli.test_formatter
"""

from __future__ import annotations

import types
import typing as t

import pytest

from rampa.cli._formatter import RampaHelpFormatter


class ColorizeLineFixture(t.NamedTuple):
    """Test case for _colorize_example_line."""

    test_id: str
    input_line: str
    expected_fragments: list[str]
    unexpected_fragments: list[str]


_MOCK_THEME = types.SimpleNamespace(
    heading="<H>",
    reset="<R>",
    label="<L>",
    long_option="<LO>",
    short_option="<SO>",
    prog="<P>",
    action="<A>",
)


_COLORIZE_LINE_FIXTURES: list[ColorizeLineFixture] = [
    ColorizeLineFixture(
        test_id="prog-only",
        input_line="rampa",
        expected_fragments=["<P>rampa<R>"],
        unexpected_fragments=["<A>"],
    ),
    ColorizeLineFixture(
        test_id="prog-and-subcommand",
        input_line="rampa run",
        expected_fragments=["<P>rampa<R>", "<A>run<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="long-option-flag",
        input_line="rampa run --quiet",
        expected_fragments=["<P>rampa<R>", "<A>run<R>", "<LO>--quiet<R>"],
        unexpected_fragments=["<L>"],
    ),
    ColorizeLineFixture(
        test_id="long-option-with-value",
        input_line="rampa run --vus 20",
        expected_fragments=["<LO>--vus<R>", "<L>20<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="long-option-flag-only",
        input_line="rampa run --quiet",
        expected_fragments=["<P>rampa<R>", "<A>run<R>"],
        unexpected_fragments=["<L>"],
    ),
    ColorizeLineFixture(
        test_id="multiple-options",
        input_line="rampa run --vus 10 --duration 1m",
        expected_fragments=[
            "<LO>--vus<R>",
            "<L>10<R>",
            "<LO>--duration<R>",
            "<L>1m<R>",
        ],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="bare-argument",
        input_line="rampa run load_test.py",
        expected_fragments=["<P>rampa<R>", "<A>run<R>"],
        unexpected_fragments=["<LO>", "<L>"],
    ),
]


@pytest.mark.parametrize(
    list(ColorizeLineFixture._fields),
    _COLORIZE_LINE_FIXTURES,
    ids=[f.test_id for f in _COLORIZE_LINE_FIXTURES],
)
def test_colorize_example_line(
    test_id: str,
    input_line: str,
    expected_fragments: list[str],
    unexpected_fragments: list[str],
) -> None:
    """Formatter colorizes example command lines correctly."""
    formatter = RampaHelpFormatter("rampa")
    result = formatter._colorize_example_line(
        input_line,
        theme=_MOCK_THEME,
        expect_value=False,
    )
    for fragment in expected_fragments:
        assert fragment in result.text, f"Expected {fragment!r} in {result.text!r}"
    for fragment in unexpected_fragments:
        assert fragment not in result.text, f"Expected {fragment!r} NOT in {result.text!r}"


def test_fill_text_without_theme() -> None:
    """Without theme, _fill_text falls through to base class."""
    formatter = RampaHelpFormatter("rampa")
    result = formatter._fill_text("hello world", 80, "")
    assert "hello world" in result
    assert "<" not in result


def test_fill_text_with_examples_heading() -> None:
    """With theme, examples: heading is colorized."""
    formatter = RampaHelpFormatter("rampa")
    formatter._theme = _MOCK_THEME  # ty: ignore[unresolved-attribute]

    text = "Some description.\n\nexamples:\n  rampa run load_test.py"
    result = formatter._fill_text(text, 80, "")

    assert "<H>examples:<R>" in result
    assert "<P>rampa<R>" in result
    assert "<A>run<R>" in result


def test_fill_text_with_named_examples() -> None:
    """Named example sections (e.g. 'run examples:') are colorized."""
    formatter = RampaHelpFormatter("rampa")
    formatter._theme = _MOCK_THEME  # ty: ignore[unresolved-attribute]

    text = "Description.\n\nrun examples:\n  rampa run test.py"
    result = formatter._fill_text(text, 80, "")

    assert "<H>run examples:<R>" in result
