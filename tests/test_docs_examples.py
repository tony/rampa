"""Executable smoke tests for selected documentation examples."""

from __future__ import annotations

import pathlib
import re
import textwrap
import typing as t

import pytest

from rampa.loader import TestPlan, load_test

ROOT = pathlib.Path(__file__).resolve().parents[1]
_PYTHON_FENCE_RE = re.compile(r"```python\n(?P<code>.*?)\n```", re.DOTALL)


class ScriptExampleCase(t.NamedTuple):
    """Documentation example that should load as a rampa script."""

    test_id: str
    path: str
    block_indexes: tuple[int, ...]
    expected_scenarios: set[str]


class PageExampleCase(t.NamedTuple):
    """Documentation page whose Python snippets should execute."""

    test_id: str
    path: str
    prelude: str


_SCRIPT_EXAMPLE_CASES: list[ScriptExampleCase] = [
    ScriptExampleCase(
        test_id="readme-quick-start",
        path="README.md",
        block_indexes=(0,),
        expected_scenarios={"default"},
    ),
    ScriptExampleCase(
        test_id="readme-full-example",
        path="README.md",
        block_indexes=(1,),
        expected_scenarios={"load"},
    ),
    ScriptExampleCase(
        test_id="getting-started",
        path="docs/getting-started/index.md",
        block_indexes=(0, 1),
        expected_scenarios={"default"},
    ),
    ScriptExampleCase(
        test_id="library-tutorial",
        path="docs/library/tutorial.md",
        block_indexes=(0, 1, 2, 3, 4, 5, 6),
        expected_scenarios={"default", "smoke", "load"},
    ),
    ScriptExampleCase(
        test_id="thresholds-script",
        path="docs/library/thresholds.md",
        block_indexes=(1,),
        expected_scenarios={"default"},
    ),
]

_PAGE_EXAMPLE_CASES: list[PageExampleCase] = [
    PageExampleCase(
        test_id="executor-snippets",
        path="docs/library/executors.md",
        prelude="",
    ),
    PageExampleCase(
        test_id="protocol-snippets",
        path="docs/library/protocols.md",
        prelude="",
    ),
    PageExampleCase(
        test_id="threshold-config-snippet",
        path="docs/library/thresholds.md",
        prelude="",
    ),
]


def _python_blocks(path: str) -> list[str]:
    """Return Python fenced blocks from a documentation file."""
    content = (ROOT / path).read_text()
    return [match.group("code") for match in _PYTHON_FENCE_RE.finditer(content)]


def _write_script(
    tmp_path: pathlib.Path,
    case: ScriptExampleCase,
) -> pathlib.Path:
    """Write selected documentation blocks to a temporary script."""
    blocks = _python_blocks(case.path)
    script = tmp_path / f"{case.test_id}.py"
    script.write_text("\n\n".join(blocks[index] for index in case.block_indexes))
    return script


def _load_example_script(
    tmp_path: pathlib.Path,
    case: ScriptExampleCase,
) -> TestPlan:
    """Load a temporary rampa script built from documentation snippets."""
    script = _write_script(tmp_path, case)
    return load_test(str(script))


@pytest.mark.parametrize(
    "case",
    _SCRIPT_EXAMPLE_CASES,
    ids=lambda case: case.test_id,
)
def test_documented_scenario_scripts_load(
    case: ScriptExampleCase,
    tmp_path: pathlib.Path,
) -> None:
    """Complete scenario examples load through the public script loader."""
    plan = _load_example_script(tmp_path, case)
    assert set(plan.scenarios) == case.expected_scenarios


@pytest.mark.parametrize(
    "case",
    _PAGE_EXAMPLE_CASES,
    ids=lambda case: case.test_id,
)
def test_documented_python_snippets_execute(case: PageExampleCase) -> None:
    """Standalone page snippets compile and execute without API drift."""
    for block in _python_blocks(case.path):
        namespace: dict[str, t.Any] = {"__name__": f"_docs_{case.test_id}"}
        code = case.prelude + "\n" + textwrap.dedent(block)
        exec(compile(code, f"{case.path}:{case.test_id}", "exec"), namespace)
