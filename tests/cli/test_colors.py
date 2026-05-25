"""Tests for rampa CLI color utilities.

>>> import tests.cli.test_colors
"""

from __future__ import annotations

import typing as t

import pytest

from rampa.cli._colors import (
    ColorMode,
    Colors,
    build_description,
    get_color_mode,
    strip_ansi,
    style,
)


class ColorModeFixture(t.NamedTuple):
    """Test case for color mode resolution."""

    test_id: str
    mode: ColorMode
    env_no_color: str | None
    env_force_color: str | None
    env_python_colors: str | None
    expected_enabled: bool


_COLOR_MODE_FIXTURES: list[ColorModeFixture] = [
    ColorModeFixture(
        test_id="never",
        mode=ColorMode.NEVER,
        env_no_color=None,
        env_force_color=None,
        env_python_colors=None,
        expected_enabled=False,
    ),
    ColorModeFixture(
        test_id="always",
        mode=ColorMode.ALWAYS,
        env_no_color=None,
        env_force_color=None,
        env_python_colors=None,
        expected_enabled=True,
    ),
    ColorModeFixture(
        test_id="no-color-overrides-always",
        mode=ColorMode.ALWAYS,
        env_no_color="1",
        env_force_color=None,
        env_python_colors=None,
        expected_enabled=False,
    ),
    ColorModeFixture(
        test_id="force-color-auto",
        mode=ColorMode.AUTO,
        env_no_color=None,
        env_force_color="1",
        env_python_colors=None,
        expected_enabled=True,
    ),
    ColorModeFixture(
        test_id="no-color-beats-force",
        mode=ColorMode.AUTO,
        env_no_color="1",
        env_force_color="1",
        env_python_colors=None,
        expected_enabled=False,
    ),
    ColorModeFixture(
        test_id="python-colors-0-disables",
        mode=ColorMode.AUTO,
        env_no_color=None,
        env_force_color=None,
        env_python_colors="0",
        expected_enabled=False,
    ),
    ColorModeFixture(
        test_id="python-colors-1-enables",
        mode=ColorMode.AUTO,
        env_no_color=None,
        env_force_color=None,
        env_python_colors="1",
        expected_enabled=True,
    ),
    ColorModeFixture(
        test_id="no-color-beats-python-colors",
        mode=ColorMode.AUTO,
        env_no_color="1",
        env_force_color=None,
        env_python_colors="1",
        expected_enabled=False,
    ),
    ColorModeFixture(
        test_id="python-colors-0-overrides-always",
        mode=ColorMode.ALWAYS,
        env_no_color=None,
        env_force_color=None,
        env_python_colors="0",
        expected_enabled=False,
    ),
]


@pytest.mark.parametrize(
    list(ColorModeFixture._fields),
    _COLOR_MODE_FIXTURES,
    ids=[f.test_id for f in _COLOR_MODE_FIXTURES],
)
def test_color_mode_resolution(
    test_id: str,
    mode: ColorMode,
    env_no_color: str | None,
    env_force_color: str | None,
    env_python_colors: str | None,
    expected_enabled: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Color mode respects env vars and explicit modes."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("PYTHON_COLORS", raising=False)
    if env_no_color is not None:
        monkeypatch.setenv("NO_COLOR", env_no_color)
    if env_force_color is not None:
        monkeypatch.setenv("FORCE_COLOR", env_force_color)
    if env_python_colors is not None:
        monkeypatch.setenv("PYTHON_COLORS", env_python_colors)

    colors = Colors(mode)
    assert colors._enabled is expected_enabled


def test_colors_never_returns_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Colors with NEVER mode returns text unchanged."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    colors = Colors(ColorMode.NEVER)
    assert colors.success("ok") == "ok"
    assert colors.error("fail") == "fail"
    assert colors.info("note") == "note"
    assert colors.warning("warn") == "warn"
    assert colors.highlight("hi") == "hi"
    assert colors.muted("lo") == "lo"


def test_colors_always_returns_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Colors with ALWAYS mode returns text with ANSI codes."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    colors = Colors(ColorMode.ALWAYS)
    result = colors.success("ok")
    assert "\033[" in result
    assert "ok" in result


def test_style_with_fg() -> None:
    """style() applies foreground color."""
    result = style("hello", fg="green")
    assert "\033[32m" in result
    assert "hello" in result
    assert "\033[0m" in result


def test_style_with_bold() -> None:
    """style() applies bold."""
    result = style("hello", bold=True)
    assert "\033[1m" in result


def test_strip_ansi() -> None:
    """strip_ansi removes ANSI codes."""
    assert strip_ansi("\033[32mgreen\033[0m") == "green"
    assert strip_ansi("plain") == "plain"


class GetColorModeFixture(t.NamedTuple):
    """Test case for get_color_mode."""

    test_id: str
    arg: str | None
    expected: ColorMode


_GET_COLOR_MODE_FIXTURES: list[GetColorModeFixture] = [
    GetColorModeFixture(test_id="none", arg=None, expected=ColorMode.AUTO),
    GetColorModeFixture(test_id="auto", arg="auto", expected=ColorMode.AUTO),
    GetColorModeFixture(test_id="always", arg="always", expected=ColorMode.ALWAYS),
    GetColorModeFixture(test_id="never", arg="never", expected=ColorMode.NEVER),
    GetColorModeFixture(test_id="invalid", arg="invalid", expected=ColorMode.AUTO),
    GetColorModeFixture(test_id="upper", arg="ALWAYS", expected=ColorMode.ALWAYS),
]


@pytest.mark.parametrize(
    list(GetColorModeFixture._fields),
    _GET_COLOR_MODE_FIXTURES,
    ids=[f.test_id for f in _GET_COLOR_MODE_FIXTURES],
)
def test_get_color_mode(
    test_id: str,
    arg: str | None,
    expected: ColorMode,
) -> None:
    """get_color_mode resolves string arguments to ColorMode."""
    assert get_color_mode(arg) == expected


def test_build_description_basic() -> None:
    """build_description assembles intro and example blocks."""
    result = build_description("My tool.", [(None, ["mytool run"])])
    assert "My tool." in result
    assert "examples:" in result
    assert "  mytool run" in result


def test_build_description_named_section() -> None:
    """build_description uses heading in section title."""
    result = build_description("Tool.", [("sync", ["tool sync"])])
    assert "sync examples:" in result


def test_build_description_empty_intro() -> None:
    """build_description handles empty intro."""
    result = build_description("", [(None, ["cmd"])])
    assert result.startswith("examples:")
