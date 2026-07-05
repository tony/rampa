"""Contract tests for examples and generated documentation shims."""

from __future__ import annotations

import inspect
import pathlib
import re
import typing as t

import pytest

from rampa.mcp import tools as runtime_tools

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RequiredTextCase(t.NamedTuple):
    """Required text in a documentation file."""

    test_id: str
    path: str
    text: str


class ForbiddenTextCase(t.NamedTuple):
    """Forbidden stale text in a documentation file."""

    test_id: str
    path: str
    text: str


_REQUIRED_TEXT_CASES: list[RequiredTextCase] = [
    RequiredTextCase(
        test_id="cli-index-links-inspect",
        path="docs/cli/index.md",
        text="inspect",
    ),
    RequiredTextCase(
        test_id="check-docs-file-not-found-exit",
        path="docs/cli/check.md",
        text="1 | Validation error, import failure, or file not found",
    ),
    RequiredTextCase(
        test_id="pytest-docs-current-scenario-fields",
        path="docs/pytest/index.md",
        text="`pre_allocated_vus`, `max_vus`, `exec_fn`, `start_time`,",
    ),
]

_FORBIDDEN_TEXT_CASES: list[ForbiddenTextCase] = [
    ForbiddenTextCase(
        test_id="readme-no-scenario-export",
        path="README.md",
        text="from rampa import Config, Scenario",
    ),
    ForbiddenTextCase(
        test_id="distributed-no-archive-cli",
        path="docs/library/distributed.md",
        text="rampa archive create",
    ),
    ForbiddenTextCase(
        test_id="check-docs-no-file-not-found-exit-2",
        path="docs/cli/check.md",
        text="2 | File not found",
    ),
]


ToolCallable = t.Callable[..., t.Awaitable[t.Any]]


class FakeMCP:
    """Minimal MCP tool collector for registration contract tests."""

    def __init__(self) -> None:
        self.tool_names: list[str] = []

    def tool(
        self,
        *,
        name: str,
        description: str,
    ) -> t.Callable[[ToolCallable], ToolCallable]:
        """Collect a registered tool callback."""
        _ = description

        def decorator(func: ToolCallable) -> ToolCallable:
            self.tool_names.append(name)
            return func

        return decorator


@pytest.mark.parametrize(
    "case",
    _REQUIRED_TEXT_CASES,
    ids=lambda case: case.test_id,
)
def test_docs_contain_required_contract_text(case: RequiredTextCase) -> None:
    """Documentation files include required public-surface text."""
    content = (ROOT / case.path).read_text()
    assert case.text in content


@pytest.mark.parametrize(
    "case",
    _FORBIDDEN_TEXT_CASES,
    ids=lambda case: case.test_id,
)
def test_docs_do_not_contain_stale_contract_text(case: ForbiddenTextCase) -> None:
    """Documentation files do not keep known-stale public-surface text."""
    content = (ROOT / case.path).read_text()
    assert case.text not in content


def test_mcp_tool_docs_match_runtime_registration() -> None:
    """MCP tool docs and docs-only shim cover every runtime tool."""
    mcp = FakeMCP()
    runtime_tools.register(t.cast(t.Any, mcp))
    runtime_names = set(mcp.tool_names)

    tools_doc = (ROOT / "docs/mcp/tools.md").read_text()
    documented_names = set(re.findall(r"```{fastmcp-tool} ([a-z_]+)", tools_doc))

    from docs._ext import rampa_fastmcp

    shim_names = {
        namespace.name
        for _name, func in inspect.getmembers(rampa_fastmcp, inspect.iscoroutinefunction)
        if (namespace := getattr(func, "__fastmcp__", None)) is not None
    }

    assert documented_names == runtime_names
    assert shim_names == runtime_names
