# AGENTS.md

This file provides guidance to AI agents (including Claude Code, Cursor, and other LLM-powered tools) when working with code in this repository.

## CRITICAL REQUIREMENTS

### Test Success
- ALL tests MUST pass for code to be considered complete and working
- Never describe code as "working as expected" if there are ANY failing tests
- Even if specific feature tests pass, failing tests elsewhere indicate broken functionality
- Changes that break existing tests must be fixed before considering implementation complete
- A successful implementation must pass linting, type checking, AND all existing tests

## Project Overview

rampa is a load testing framework for Python.

## Engineering Policies

### Python First

Python is the default implementation language, public API surface, and user
experience for this project. Start with clear, typed Python before reaching for
native code. Native implementation is appropriate only for measured hot paths,
control/latency-sensitive internals, or platform interfaces that Python cannot
reasonably handle on its own.

### Strict Typing

Types are part of the design, not cleanup after the fact. Avoid `Any` and
`object` unless there is no narrower honest type available, such as a true
trust boundary, intentionally generic callback, or untyped third-party API.
When `Any` or `object` is unavoidable, keep it local, validate or narrow it as
soon as possible, and do not let it leak into public APIs or shared internal
contracts.

### Benchmarking Against Trunk, Tags, and Releases

Performance claims must name the comparison baseline. Use trunk for active
development comparisons, tags and releases for release-facing claims, major
versions for schema-breaking benchmark changes, and minor versions for
non-schema-breaking benchmark changes such as added fields.

High-level benchmark results may be stored in the repository when they are part
of the supported evidence surface. Keep large traces, dumps, profiler captures,
and deep-dive notes out of tracked files; put those details in PR comments or
external artifacts where they can support review without bloating the tree.

### Profiling One Command Away

Profiling must be easy to run when performance or latency work is in scope. A
developer or agent should be able to profile a test, profile normal runtime
usage, record profiler output, and inspect the result through documented
commands or scripts without inventing a workflow from scratch.

## Native Boundary Policy

Native boundary shapes and the rules for choosing them are ADR 002 (domain-agnostic); the
load-testing constraints below are ADR 003.

Default to no native code. Prove the bottleneck first: a measurement of the user-visible path,
against a named baseline, must show a performance, latency, scale, memory, reliability, or
platform-interface limit Python cannot resolve algorithmically or structurally before you reach
for Rust. Native code must not define public behavior, add public API, or be required to
install, import, or run the package.

Classify the boundary, not the component, before writing native code. Take the narrowest shape
that honestly fits:

1. Accelerator - a drop-in for a public Python callable. Removing the native build changes
   nothing observable except speed. Follows ADR 001.
2. Engine - in-process native code that executes a normalized plan or batch the Python runtime
   builds; runs to completion, no user Python in the hot loop; may be approximate, tested
   within a documented tolerance. Follows ADR 002.
3. Worker - an independent process, binary, or long-lived native thread behind a versioned
   message-passing protocol. A separate execution mode, not a hidden accelerator; its execution
   mode and protocol ship under a follow-up ADR. Follows ADR 002.

A component exposing more than one boundary must satisfy every shape it touches. On a genuine
tie between two adjacent shapes for one boundary, take the stricter (engine over accelerator,
worker over engine); never round down. A boundary that fits none is not designed yet.

Do not cross an engine or worker boundary inside per-request, per-event, per-sample, or
per-node loops unless a user-visible benchmark proves the cost is acceptable, and do not call
user Python from a native hot loop. Prefer plans, batches, buffers, and protocol messages.
Release the interpreter lock during heavy native work that touches no Python objects.

Load-test integrity (ADR 003): native code must not change what a load test measures. Preserve
timing (monotonic), scheduling (scheduled vs actual start time, coordinated omission),
timeout/cancellation/retry classification, connection accounting, and percentile/aggregation
semantics. A load generator's per-request path is usually I/O-bound; target measured bottlenecks
(scheduling, serialization, TLS, metrics reduction), not the request loop. Arbitrary user
scenarios run in the Python runtime; a native execution mode runs a declarative scenario subset
— explicit, opt-in, never a silent fallback.

Keep native logic in a core with no Python-binding dependency; keep the binding thin and
separate. The base package must install, import, and run without native code unless an ADR
explicitly changes that policy; do not split native artifacts into separate user-facing
distributions without documenting the trigger.

## Self-Measurement Policy

How rampa tests, benchmarks, and profiles itself is policy, not ad-hoc tooling: ADR 004
(self-harnessing), ADR 005 (self-benchmarking), and ADR 006 (self-profiling) in docs/adrs/. They
make the native-boundary preconditions above enforceable rather than aspirational. A load
generator's own cost competes with what it measures, so the rule across all three is: detect
regressions deterministically by counting, and measure wall-clock latency separately and on demand.

Self-harness (ADR 004). Test the framework by running it end-to-end against a controllable target
and asserting exact outcomes — request distribution, metric aggregates, threshold verdicts — not
"ran without raising." The shared behavioral suite runs against both the pure-Python and native
paths; CI runs a mandatory Python-only job. Make tests deterministic by construction: injected
monotonic clock, seeded randomness, pinned ports, repeat-and-diff leak checks.

Self-benchmark (ADR 005). Catch regressions on every pull request by counting — function calls,
allocations, events, connections — against a checked-in baseline keyed by environment and by
whether the accelerator is present; counts are deterministic, so they never flake on a busy CI
machine. Measure wall-clock latency and throughput separately: against a named baseline (trunk,
tag, release), reported as a geometric mean, run deliberately on a controlled machine rather than
on every pull request. Native code requires such a measurement of the user-visible path against a
named baseline first.

Self-profile (ADR 006). Profiling a test, a run, or the native accelerator is one documented
command, defaults to zero-dependency standard-library tooling, emits a standard format, and prints
how to inspect it. Distinguish wall vs CPU vs GIL time; keep instrumentation zero-overhead when
off; profile release-shaped builds; never let profiling change what a load test measures.

## Pure Python / Rust Accelerator Compatibility

This project is Python-first. The pure Python implementation is the reference implementation. Rust is an optional accelerator and must not redefine public behavior.

### Required engineering policy

- Implement every public API in pure Python before adding Rust acceleration.
- Treat the Python implementation as the semantic source of truth.
- Keep Rust acceleration optional. The package must import, install, and pass tests without the Rust extension.
- Do not expose public Rust-only functions, classes, attributes, argument forms, return shapes, or behaviors.
- Run the same behavioral tests against both the pure Python path and the Rust-accelerated path.
- Preserve Python duck typing. If Python accepts an iterable, mapping, sequence, path-like object, buffer-like object, subclass, or file-like object, Rust must not narrow that contract.
- Preserve observable behavior: return values, return types where public, exceptions, mutation, ordering, equality, hashing, warnings, serialization, context-manager behavior, and async behavior.
- Rust-specific tests are allowed, but they do not replace shared compatibility tests.
- Public documentation and type hints describe the Python API, not Rust internals.
- `unsafe` Rust must be minimal, justified with a nearby `SAFETY:` comment, and covered by relevant tests.

### Import and fallback rule

The public Python module owns the API. It may replace selected Python objects with Rust equivalents only after the Python implementation has already defined them.

Preferred pattern:

```python
from ._module_py import parse, normalize, Token

_HAS_RUST_ACCELERATOR = False

try:
    from ._native import parse as parse
    from ._native import normalize as normalize
except ImportError:
    pass
else:
    _HAS_RUST_ACCELERATOR = True
```

Do not use broad fallback in normal imports:

```python
# Avoid: this can hide real defects in the Rust extension.
try:
    from ._native import parse
except Exception:
    from ._module_py import parse
```

Tests may deliberately fail on unexpected Rust import errors so native defects are not silently masked.

### Compatibility test requirement

Each accelerated API must have shared behavioral tests that run against both implementations.

Recommended `pytest` shape:

```python
import pytest

from package_name import _module_py

try:
    from package_name import _native
except ImportError:
    _native = None


@pytest.fixture(params=[_module_py, _native], ids=["python", "rust"])
def impl(request):
    if request.param is None:
        pytest.skip("Rust accelerator is not available")
    return request.param


def test_parse_empty_input(impl):
    assert impl.parse("") == []


def test_parse_invalid_input(impl):
    with pytest.raises(ValueError):
        impl.parse("\x00")
```

Tests must include normal cases, empty inputs, boundary values, invalid inputs, subclass or duck-typed inputs where relevant, mutation and aliasing behavior, repeated calls, large inputs, Unicode or binary edge cases, and error paths.

### CI requirement

CI must exercise both modes:

```text
Python-only job:
  - install without the Rust extension or force the Python fallback
  - run the full shared behavioral test suite

Rust-enabled job:
  - build/install the Rust extension
  - run the same shared behavioral test suite
  - run Rust-specific tests where applicable
```

A green Rust-enabled job does not compensate for a broken Python-only job.

### Pull request checklist

Before merging a change that adds or modifies Rust acceleration, confirm:

```text
[ ] Public behavior exists first in pure Python.
[ ] Shared tests cover the Python behavior.
[ ] The same tests pass with Rust enabled.
[ ] The package imports and runs without Rust.
[ ] Rust exposes no additional public API.
[ ] Error behavior matches the Python implementation.
[ ] Duck-typed inputs remain supported.
[ ] Type hints and documentation remain accurate.
[ ] Benchmarks or a clear performance rationale justify the accelerator.
[ ] Unsafe Rust, if present, is documented and reviewed.
```

Final rule: Rust may make this project faster. Rust must not make it less Pythonic, less portable, less tested, or less predictable.

## Development Environment

This project uses:
- Python 3.14+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [ty](https://github.com/astral-sh/ty) for type checking
- [pytest](https://docs.pytest.org/) for testing
  - [pytest-watcher](https://github.com/olzhasar/pytest-watcher) for continuous testing

## Common Commands

### Setting Up Environment

```bash
# Install dependencies
uv sync

# Install with development dependencies
uv sync --all-groups
```

### Running Tests

```bash
# Run all tests
just test
# or directly with pytest
uv run pytest

# Run a single test file
uv run pytest tests/test_example.py

# Run a specific test
uv run pytest tests/test_example.py::test_function

# Run tests with test watcher
just start
# or
uv run ptw .

# Run tests with doctests
uv run ptw . --now --doctest-modules
```

### Linting and Type Checking

```bash
# Run ruff for linting
just ruff
# or directly
uv run ruff check .

# Format code with ruff
just ruff-format
# or directly
uv run ruff format .

# Run ruff linting with auto-fixes
uv run ruff check . --fix --show-fixes

# Run ty for type checking
just ty
# or directly
uv run ty check

# Watch mode for linting (using entr)
just watch-ruff
just watch-ty
```

### Development Workflow

Follow this workflow for code changes:

1. **Format First**: `uv run ruff format .`
2. **Run Tests**: `uv run pytest`
3. **Run Linting**: `uv run ruff check . --fix --show-fixes`
4. **Check Types**: `uv run ty check`
5. **Verify Tests Again**: `uv run pytest`

### Documentation

```bash
# Build documentation
just build-docs

# Start documentation server with auto-reload
just start-docs
```

## Code Architecture

```
src/rampa/
  __init__.py          # Package entry point
  py.typed             # PEP 561 type marker
```

## Testing Strategy

All tests are plain functions (`def test_*`). No `class TestFoo:` groupings. Every test
function and every `NamedTuple` fixture class must be fully type-annotated; ty runs as
part of CI.

Run continuously while developing:

```console
$ uv run ptw .
```

Include doctests:

```console
$ uv run ptw . --now --doctest-modules
```

### Type Annotations (required everywhere)

Every test function must annotate all parameters and the return type:

```python
def test_something(value: str, expected: int) -> None:
    assert compute(value) == expected
```

Every `NamedTuple` fixture class must annotate all fields.

### NamedTuple Parametrization

Use `t.NamedTuple` for any parametrized test with three or more inputs. Two wiring
styles are in use — pick whichever reads more clearly for the case at hand.

**Style A — unpack all fields** (dominant):

Each field becomes a typed parameter in the test function, which makes the signature
self-documenting:

```python
import typing as t

import pytest


class FooFixture(t.NamedTuple):
    """Test case for foo()."""

    test_id: str  # always the first field
    input: str
    expected: str


_FOO_FIXTURES: list[FooFixture] = [
    FooFixture(test_id="basic", input="a", expected="A"),
    FooFixture(test_id="empty", input="", expected=""),
]


@pytest.mark.parametrize(
    list(FooFixture._fields),
    _FOO_FIXTURES,
    ids=[f.test_id for f in _FOO_FIXTURES],
)
def test_foo(test_id: str, input: str, expected: str) -> None:
    """foo() uppercases its input."""
    assert foo(input) == expected
```

**Style B — pass whole struct as `case`** (when the struct is reused in assertion
messages or has many fields):

```python
@pytest.mark.parametrize(
    "case",
    _FOO_FIXTURES,
    ids=lambda c: c.test_id,
)
def test_foo(case: FooFixture) -> None:
    """foo() uppercases its input."""
    assert foo(case.input) == case.expected
```

Naming conventions:

- `test_id: str` is **always the first field**
- Fixture list: `_FOO_FIXTURES` (module-private, all-caps)
- Fixture class: `FooFixture` or `FooCase` — never `TestFoo`

### Available Fixtures Reference

| Fixture | Source | When to use |
|---|---|---|
| `tmp_path` | pytest built-in | Per-test temp directory |
| `tmp_path_factory` | pytest built-in | Session/module fixtures that create temp dirs |
| `monkeypatch` | pytest built-in | Env vars, module attributes, `sys.modules` patching |
| `caplog` | pytest built-in | Log assertions; use `caplog.records`, not `caplog.text` |

### Anti-Patterns

- **No `class TestFoo:` groupings** — use descriptive function names and file
  organization instead
- **No `unittest.mock.patch`** — use `monkeypatch`
- **No `tempfile.mkdtemp()`** — use `tmp_path`
- **No unannotated test functions** — every parameter and `-> None` must be typed
- **No `# doctest: +SKIP`** in module doctests (see Doctests section)
- **No inline tuples in `parametrize`** when there are three or more fields — use
  `NamedTuple`

## Coding Standards

Key highlights:

### Imports

- **Use namespace imports for standard library modules**: `import enum` instead of `from enum import Enum`
  - **Exception**: `dataclasses` module may use `from dataclasses import dataclass, field` for cleaner decorator syntax
  - This rule applies to Python standard library only; third-party packages may use `from X import Y`
- **For typing**, use `import typing as t` and access via namespace: `t.NamedTuple`, etc.
- **Use `from __future__ import annotations`** at the top of all Python files

### Docstrings

Follow NumPy docstring style for all functions and methods:

```python
"""Short description of the function or class.

Detailed description using reStructuredText format.

Parameters
----------
param1 : type
    Description of param1
param2 : type
    Description of param2

Returns
-------
type
    Description of return value
"""
```

### Doctests

**All functions and methods MUST have working doctests.** Doctests serve as both documentation and tests.

**CRITICAL RULES:**
- Doctests MUST actually execute - never comment out function calls or similar
- Doctests MUST NOT be converted to `.. code-block::` as a workaround (code-blocks don't run)
- If you cannot create a working doctest, **STOP and ask for help**

**Available tools for doctests:**
- `doctest_namespace` fixtures (from conftest.py): `tmp_path`
- Ellipsis for variable output: `# doctest: +ELLIPSIS`
- Update `conftest.py` to add new fixtures to `doctest_namespace`

**`# doctest: +SKIP` is NOT permitted** - it's just another workaround that doesn't test anything.

### Logging Standards

These rules guide future logging changes; existing code may not yet conform.

#### Logger setup

- Use `logging.getLogger(__name__)` in every module
- Add `NullHandler` in library `__init__.py` files
- Never configure handlers, levels, or formatters in library code -- that's the application's job

#### Lazy formatting

`logger.debug("msg %s", val)` not f-strings. Two rationales:
- Deferred string interpolation: skipped entirely when level is filtered
- Aggregator message template grouping: `"Running %s"` is one signature grouped x10,000; f-strings make each line unique

When computing `val` itself is expensive, guard with `if logger.isEnabledFor(logging.DEBUG)`.

#### Log levels

| Level | Use for | Examples |
|-------|---------|----------|
| `DEBUG` | Internal mechanics | Request scheduling, connection pool state |
| `INFO` | User-visible operations | Test started, results summary |
| `WARNING` | Recoverable issues, deprecation | Connection retry, deprecated option |
| `ERROR` | Failures that stop an operation | Target unreachable, invalid config |

#### Message style

- Lowercase, past tense for events: `"request sent"`, `"connection established"`
- No trailing punctuation
- Keep messages short; put details in `extra`, not the message string

#### Exception logging

- Use `logger.exception()` only inside `except` blocks when you are **not** re-raising
- Use `logger.error(..., exc_info=True)` when you need the traceback outside an `except` block
- Avoid `logger.exception()` followed by `raise` -- this duplicates the traceback

#### Testing logs

Assert on `caplog.records` attributes, not string matching on `caplog.text`:
- Scope capture: `caplog.at_level(logging.DEBUG, logger="rampa.core")`
- Filter records rather than index by position
- `caplog.record_tuples` cannot access extra fields -- always use `caplog.records`

#### Avoid

- f-strings/`.format()` in log calls
- Catch-log-reraise without adding new context
- `print()` for diagnostics
- Logging secret env var values (log key names only)

### Git Commit Standards

Format commit messages as:
```
Scope(type[detail]): concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject ≤50 chars (excluding any trailing `(#NN)` PR ref); wrap
body lines at ≤72 chars. Separate the `why:` and `what:` blocks with a
blank line.

Common commit types:
- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting
- **py(deps)**: Dependencies
- **py(deps[dev])**: Dev Dependencies
- **ai(rules[AGENTS])**: AI rule updates
- **ai(claude[rules])**: Claude Code rules (CLAUDE.md)
- **ai(claude[command])**: Claude Code command changes

Example:
```
rampa(feat[runner]): Add concurrent request scheduler

why: Enable parallel load generation across multiple workers

what:
- Add RequestScheduler with configurable concurrency
- Implement rate limiting with token bucket algorithm
- Add tests for scheduler behavior under load
```
#### Release commits

Never create tags. Never push tags. The user handles tagging and tag
pushes (tags trigger the CI publish workflow).

Release commit subjects are plain and short: `Tag v<version>`. Put
the detailed why/what in the commit body. Don't use the
`Scope(type[detail]):` format for releases — don't bury the lede.

For multi-line commits, use heredoc to preserve formatting:
```bash
git commit -m "$(cat <<'EOF'
feat(Component[method]) add feature description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

## Documentation Standards

### Code Blocks in Documentation

When writing documentation (README, CHANGES, docs/), follow these rules for code blocks:

**One command per code block.** This makes commands individually copyable. For sequential commands, either use separate code blocks or chain them with `&&` or `;` and `\` continuations (keeping it one logical command).

**Put explanations outside the code block**, not as comments inside.

Good:

Run the tests:

```console
$ uv run pytest
```

Run with coverage:

```console
$ uv run pytest --cov
```

Bad:

```console
# Run the tests
$ uv run pytest

# Run with coverage
$ uv run pytest --cov
```

### Shell Command Formatting

These rules apply to shell commands in documentation (README, CHANGES, docs/), **not** to Python doctests.

**Use `console` language tag with `$ ` prefix.** This distinguishes interactive commands from scripts and enables prompt-aware copy in many terminals.

Good:

```console
$ uv run pytest
```

Bad:

```bash
uv run pytest
```

**Split long commands with `\` for readability.** Each flag or flag+value pair gets its own continuation line, indented. Positional parameters go on the final line.

### Changelog Conventions

These rules apply when authoring entries in `CHANGES`, which is rendered as the Sphinx changelog page. Modeled on Django's release-notes shape — deliverables get titles and prose, not bullets.

**Release entry boilerplate.** Every release header is `## rampa X.Y.Z (YYYY-MM-DD)`. The file opens with a `## rampa X.Y.Z (unreleased)` block prefaced by a single `<!-- To maintainers and contributors: Please add notes for the forthcoming version below -->` HTML comment — new release entries land below the most recent released entry, never between the comment and the unreleased header.

**Open with a multi-sentence lead paragraph.** Plain prose, no italic. Open with the version as sentence subject (*"rampa X.Y.Z ships …"*) so the lead is self-contained when excerpted. Two to four sentences telling the reader what shipped and who cares — user-visible takeaways, not internal mechanism. Cross-reference detail docs with `{ref}` to keep the lead compact.

**Each deliverable is a section, not a bullet.** Inside `### What's new`, every distinct deliverable gets a `#### Deliverable title` heading naming it in user vocabulary, followed by 1-3 prose paragraphs explaining what shipped. Don't wrap a paragraph in `- ` — bullets are for enumerable lists, not paragraph containers. Cross-link detail docs (`See {ref}\`foo\` for details.`) so prose stays focused.

**The deliverable test.** Before writing an entry, ask: "What's the deliverable, in user vocabulary?" If you can't answer in one sentence, the entry isn't ready. Mechanism (helper internals, byte counters, schema-validation locations) belongs in PR descriptions and code comments, not the changelog.

**Fixed subheadings**, in this order when present: `### Breaking changes`, `### Dependencies`, `### What's new`, `### Fixes`, `### Documentation`, `### Development`. Dev tooling (helper scripts, internal automation) lives under `### Development`. For breaking changes, show the migration path with concrete inline code (e.g. a `# Before` / `# After` fenced code block). Dependency floor bumps use the form ``Minimum `pkg>=X.Y.Z` (was `>=X.Y.W`)``.

**PR refs `(#NN)`** sit at the end of each deliverable's prose body, not in the `####` heading.

**When bullets are appropriate.** Catch-all sections (`### Fixes`, occasionally `### Documentation`) with 3+ genuinely small items use bullets — one line each, never paragraphs. If a bullet swells past two lines, promote it to a `#### Title` heading with prose body.

**Anti-patterns.**

- Fragile metrics: token ceilings, third-party version pins, percent benchmarks, exact byte counts. Describe the *capability*, not the math.
- Internal jargon: private symbols (leading-underscore identifiers), algorithm names exposed for the first time, backend scaffolding.
- Walls of text dressed up as bullets.
- Buried breaking changes — they get their own subheading at the top of the entry.

**Always link autodoc'd APIs.** Any class, method, function, exception, or attribute that has its own rendered page must be cited via the appropriate role (`{class}`, `{meth}`, `{func}`, `{exc}`, `{attr}`) — never with plain backticks. Doc pages without explicit ref labels use `{doc}`. Plain backticks are correct for code syntax, env vars, parameter names, and file paths that aren't doc pages — anything without an autodoc destination.

**MyST roles.** Class references use `{class}`, methods use `{meth}`, functions use `{func}`, exceptions use `{exc}`, attributes use `{attr}`, internal anchors use `{ref}`, doc-path links use `{doc}`.

**Summarization style.** When a user asks "what changed in the latest version?" or similar, lead with the entry's lead paragraph (paraphrased if needed), followed by each `####` deliverable heading under `### What's new` with a one-sentence summary. Cite `(#NN)` only if the user asks for source links. Don't invent versions, dates, or numbers not present in `CHANGES`. Don't quote line numbers or file offsets — those shift as the file evolves.

## Debugging Tips

When stuck in debugging loops:

1. **Pause and acknowledge the loop**
2. **Minimize to MVP**: Remove all debugging cruft and experimental code
3. **Document the issue** comprehensively for a fresh approach
4. **Format for portability** (using quadruple backticks)

## AI Slop Prevention

Treat AI slop as **review-hostile noise**, not as proof that text or
code is wrong. The goal is to maximize information density by removing
artifacts that make the repository harder to trust or navigate.

### The Anti-Slop Rubric

Before committing, audit all AI-assisted changes for these noise
patterns:

- **AI Signatures:** Remove "Generated by", footers, conversational
  filler ("Certainly!", "Here is..."), unexplained emojis (🤖, ✨), and
  AI-tool metadata.
- **Brittle References:** Avoid hard-coded line numbers, fragile
  file/test counts, dated "as of" claims, bare SHAs, and local
  absolute paths unless they are strict evidentiary artifacts (e.g.,
  benchmark logs).
- **Diff Narration:** Do not restate what moved, was renamed, or was
  removed in artifacts the downstream reader holds: code, docstrings,
  README, CHANGES, PR descriptions, or release notes. The diff and
  commit message already carry this history.
- **Branch-Internal Narrative:** Do not mention intermediate branch
  states, abandoned approaches, or "no longer" behavior unless users
  of a published release actually experienced the old state (**The
  Published-Release Test**).
- **Low-Value Scaffolding:** Remove ownerless TODOs (`TODO: revisit`),
  unused future-proofing, debug artifacts, and defensive wrappers that
  do not protect a currently reachable failure mode.
- **Prose Inflation:** Replace generic AI "tells" like *comprehensive,
  robust, seamless, production-ready, leverage, delve, tapestry,* and
  *best practices* with concrete descriptions of behavior,
  constraints, or trade-offs.

### No Private Labeling Systems

Do not introduce or manage private shorthand labeling systems in
tracked artifacts. This applies to docs, ADRs, code comments, examples,
tests, fixtures, changelog entries, PR descriptions, release text, and
commit messages.

Avoid repo-private label schemes, ranking labels, pass labels, taxonomy
labels, shorthand buckets, or agent-only planning names unless they are
already a real public API, protocol term, metric name, version, issue or
PR reference, ADR number, or user-facing domain vocabulary. Use
descriptive nouns instead: behavior names, capability names, runtime
modes, output backends, or measured concepts.

Before committing, review new headings, tables, bullets, changelog
entries, and commit messages for shorthand labels. Classify each hit as
public vocabulary, domain metric, or slop. Remove slop at the causal
commit with `fixup!` / `amend!` and `git rebase --autosquash` when
branch history is still private.

Use shape-based scans so the policy does not seed the exact labels it is
meant to prevent:

```console
$ git diff --unified=0 main...HEAD -- AGENTS.md CHANGES docs notes src tests \
  | rg -n '^\+[^+].*(\b[A-Z][0-9]{1,3}\b|\b[A-Z]{1,3}-[0-9]{1,5}\b|\b(pass|phase|level|category|class|stage)\s+([A-Z][0-9]{0,3}|[0-9]{1,3})\b|T[O]DO|T[B]D|placeholde[r])'
```

```console
$ git log --format='%H%n%s%n%b%n---END---' main..HEAD \
  | rg -n '(\b[A-Z][0-9]{1,3}\b|\b[A-Z]{1,3}-[0-9]{1,5}\b|\b(pass|phase|level|category|class|stage)\s+([A-Z][0-9]{0,3}|[0-9]{1,3})\b|T[O]DO|T[B]D|placeholde[r])'
```

### Privacy and Local Path Hygiene

Do not commit private, workstation-specific, or environment-specific
details in tracked files, generated docs, research notes, examples,
tests, fixtures, changelog entries, PR text, or commit messages.

Before committing, check both the staged diff and the intended commit
message. Keep these out of the repository:

- **Local paths:** home directories (`~/...`, `/home/...`, `/Users/...`),
  temporary directories, editor or tool cache paths, personal checkout
  roots, and machine-specific mount points. Use repo-relative paths,
  public URLs pinned to stable tags or refs, or generic examples instead.
- **PII:** personal email addresses, phone numbers, private account IDs,
  real user names, internal hostnames, customer names, and organization
  details unless they are already part of the public project identity.
- **Secrets:** tokens, API keys, passwords, private keys, cookies,
  credentials, session IDs, and signed URLs.
- **Local-only provenance:** notes such as "from my laptop",
  workstation-specific source directories, shell history, clipboard
  contents, editor state, or paths to private notes. Move that context to
  private notes or PR discussion when it is useful but not publishable.

If a private detail already landed in a branch, remove it at the causal
commit when history is still private: use a targeted `fixup!` or
`amend!` commit and `git rebase --autosquash`. If the detail may have
left the local machine, stop and ask before rewriting history; secrets
may need rotation rather than just removal.

### Durable Source Links

Link to a pinned revision, never to trunk. A pinned permalink is not a
brittle reference; an unlinked SHA dropped into prose is. `blob/main/…`
links rot silently — the file moves, lines shift, and the anchor lands
on unrelated code while still resolving.

- Prefer a release tag (`blob/v1.4.0/…`). Most durable, and it tells
  the reader which released version the claim held for.
- Otherwise use a 7-char commit ref (`blob/9a29b1a/…`) reachable from
  trunk. Use when there is no tag or the claim is about unreleased
  code. Never a PR-head SHA — it can be rebased or garbage-collected.
- Reserve `blob/main/…` for living documents meant to always show the
  latest state, such as a contributing guide.
- Line anchors (`#L120-L145`) are only safe on a pinned ref.

### Preservation & Context

**When unsure, leave the text in place and ask.** Subjective cleanup
must never be a reason to remove load-bearing rationale.

- **Preserve the "Why":** You MUST NOT delete comments that document
  invariants, protocol constraints, platform quirks, security
  boundaries, and upstream workarounds.
- **Evidence is Immune:** Preserve exact counts, dates, and SHAs when
  they serve as evidence in benchmark results, release notes, stack
  traces, or lockfiles.
- **Behavior Over Inventory:** A useful description explains what
  changed for the *system or user*; it does not provide an inventory
  of files or functions the diff already shows.

### The Published-Release Test

Long-running branches accumulate tactical decisions — renames,
refactors, attempts-then-reverts. When deciding what counts as
branch-internal, use trunk or the parent branch as the baseline — not
intermediate states inside the current branch. Ask:

> Did users of the most recently published release ever experience
> this old name, old behavior, or bug?

If the answer is **no**, it is branch-internal narrative. Move it to
the commit message and describe only the final state in the artifact.

**Keep in shipped artifacts:**
- Deprecations and migration guides for symbols that actually shipped.
- `### Fixes` entries for bugs that affected users of a published
  release.
- Comments explaining *why the current code looks this way*
  (invariants, platform quirks) that make sense to a reader who never
  saw the previous version.

### Cleanup in Hindsight

When applying these rules retroactively from inside a feature branch,
first establish scope by diffing against the parent branch (or trunk)
to identify which commits this branch actually introduced. Then:

- **In-branch commits:** Prompt the user with two options: `fixup!`
  commits with `git rebase --autosquash` to address each causal commit
  at its source, or a single cleanup commit at branch tip.
- **Trunk/Parent commits:** Default to leaving them alone. Act only on
  explicit user instruction. If the user opts in, fold the cleanup
  into a single commit at branch tip; do not rewrite shared history.
- **Scope guard:** If cleaning prior slop would touch a colleague's
  work or expand the branch beyond its stated goal, stay in lane:
  protect the current goal and leave prior slop alone.

### Change Discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, component, helper, API, or test before adding
  a new one. Modify in place when the change fits the file's
  responsibility.
- Keep new APIs private until a caller outside the module needs them.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized high-touch module — not
  for a single-use helper or a one-line re-export.

### Keep Instructions Lean

Treat this file like code and prune it.

- Delete a line whose removal would not cause a mistake.
- Move multi-step procedures into skills, path-specific rules into
  nested AGENTS.md files, and hard limits into hooks or CI.
- Keep only non-obvious, broadly applicable defaults here. Anything a
  reader can infer from the code, a manifest, or a linter does not
  belong.
