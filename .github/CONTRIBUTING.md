# Contributing

Thanks for looking. rampa is pre-alpha (`0.0.1a1`): the API is still
moving, so the most useful contribution right now is a bug report with
a reproduction, or a note on where the documentation misled you.

How this project writes prose — README, `CHANGES`, release notes,
commit messages, docstrings, source comments, and MyST documentation —
is set out separately in [WRITING.md](WRITING.md). Read that before
changing any of it. The constraints every change is held to, and the
map of what is where, are in [AGENTS.md](../AGENTS.md).

## Getting set up

```console
$ uv sync --all-extras --all-groups
```

The Rust accelerator (`rampa._core`) builds automatically the first
time you run `pytest`: the root `conftest.py` runs
`maturin develop --uv` if `cargo` is on `PATH` and no built extension is
present yet, and falls back to the pure-Python path with a warning if
`cargo` or `maturin` is missing or the build fails. You do not need to
build it by hand.

## The gates

Format:

```console
$ uv run ruff format .
```

Lint:

```console
$ uv run ruff check . --fix --show-fixes
```

Type-check:

```console
$ uv run ty check
```

This project type-checks with [ty](https://github.com/astral-sh/ty),
not mypy.

Test:

```console
$ uv run pytest
```

Documentation is a gate, not a courtesy. Doctest examples under
`src/rampa` and `tests` run inside the same `pytest` invocation via
`--doctest-modules`; selected Markdown examples under `README.md` and
`docs/` run through a separate harness in `tests/test_docs_examples.py`
and `tests/test_docs_contracts.py`, also collected by that same
`pytest` run. There is no separate doctest step, and a green `pytest`
covers both mechanisms. Which blocks qualify, and the one mistake that
silently removes a test, are in
[WRITING.md](WRITING.md#documented-examples-that-run).

CI (`.github/workflows/tests.yml`) runs, in order: `ruff check .`,
`ruff format --check .`, `ty check --output-format github`, then
`pytest`. It is the order of record; every gate it runs has to pass
before a change is done. All of them, not a subset — a green `pytest`
next to a red `ty check` is not a passing change.

Before claiming a test or a gate works, show it failing. A gate that
has never been red is an assumption.

## Coding conventions

Beyond what `ruff` enforces automatically:

- Namespace-import the standard library: `import enum`, not
  `from enum import Enum`. Third-party packages may use
  `from x import y`. `dataclasses` is the one standard-library
  exception, for `from dataclasses import dataclass, field`.
- `import typing as t` and reference names through the namespace
  (`t.NamedTuple`, `t.Any`).
- Types are part of the design, not cleanup after the fact. Avoid
  `t.Any` and `object` unless no narrower honest type exists — a true
  trust boundary, an intentionally generic callback, or an untyped
  third-party API. When one is unavoidable, keep it local, narrow it as
  soon as possible, and do not let it leak into a public API or a
  shared internal contract. `ty check` (`error-on-warning = true`)
  catches a type error; it does not catch an honest-but-avoidable
  `Any`, so this is a review discipline, not a gate.
- Docstrings follow the NumPy convention; see
  [WRITING.md](WRITING.md#docstrings) for what to say beyond the type.

## Tests

All tests are plain functions (`def test_*`). No `class TestFoo:`
groupings — use descriptive function names and file organization
instead. Every test function and every `NamedTuple` fixture class is
fully type-annotated; `ty` runs over `tests` as well as `src` in CI.

Run continuously while developing:

```console
$ uv run ptw .
```

Include doctests in the watch loop:

```console
$ uv run ptw . --now --doctest-modules
```

**Parametrization.** Use a `t.NamedTuple` for any parametrized test
with three or more inputs — not an inline tuple. `test_id: str` is
always the first field; the fixture list is `_FOO_FIXTURES`
(module-private, all-caps); the fixture class is `FooFixture` or
`FooCase`, never `TestFoo`. Two wiring styles are in use — pick
whichever reads more clearly for the case at hand:

Unpack every field as its own typed test parameter (the dominant
style, self-documenting signature):

```python
@pytest.mark.parametrize(
    list(FooFixture._fields),
    _FOO_FIXTURES,
    ids=[f.test_id for f in _FOO_FIXTURES],
)
def test_foo(test_id: str, input: str, expected: str) -> None:
    assert foo(input) == expected
```

Or pass the whole struct as `case`, when it is reused in assertion
messages or has many fields:

```python
@pytest.mark.parametrize("case", _FOO_FIXTURES, ids=lambda c: c.test_id)
def test_foo(case: FooFixture) -> None:
    assert foo(case.input) == case.expected
```

**Fixtures.**

| Fixture           | Source           | When to use                                         |
| ------------------ | ----------------- | ----------------------------------------------------- |
| `tmp_path`         | pytest built-in   | Per-test temp directory                                |
| `tmp_path_factory`  | pytest built-in   | Session/module fixtures that create temp dirs           |
| `monkeypatch`       | pytest built-in   | Env vars, module attributes, `sys.modules` patching     |
| `caplog`            | pytest built-in   | Log assertions — use `caplog.records`, never `caplog.text` |

Assert on `caplog.records` attributes, not string matching on
`caplog.text`. Scope capture with
`caplog.at_level(logging.DEBUG, logger="rampa.core")` and filter
records rather than index by position — `caplog.record_tuples` cannot
reach `extra` fields.

**Anti-patterns.**

- No `unittest.mock.patch` — use `monkeypatch`.
- No `tempfile.mkdtemp()` — use `tmp_path`.
- No unannotated test functions — every parameter and `-> None` is
  typed.
- No `# doctest: +SKIP`, in a module doctest or anywhere else.
- No inline tuples in `parametrize` once there are three or more
  fields — use a `NamedTuple`.

## Documentation

```console
$ just build-docs
```

builds the Sphinx/MyST site under `docs/_build`. Serve it with
auto-reload while editing:

```console
$ just start-docs
```

`just build-docs` is also the only thing that catches a broken
cross-reference — build before committing a page that adds or moves an
`(anchor)=` target or a `{ref}`/`{doc}` role. `docs/_ext/` and
`docs/_widgets/` are Sphinx extensions and install-widget assets that
this project ships and maintains; they are not generated output.

## Debugging

When stuck in a debugging loop: pause and name the loop out loud,
strip the reproduction down to its minimum, and write down what you
tried before starting over with a fresh approach. Quote any pasted
output in quadruple backticks so nested code fences survive.

## Releasing

Never create tags. Never push tags. The owner handles tagging and tag
pushes, because a tag triggers the publish workflow. See
[Release commits](WRITING.md#release-commits).

Pushing a tag matching `v*` runs the `release` job in
`.github/workflows/tests.yml`: it builds the sdist and wheel with
`maturin` and publishes them to PyPI with trusted-publisher
attestations. A contributor's part of a release stops at a `CHANGES`
entry; cutting the release itself is the owner's job.

## Pull requests

One subject per pull request. Unrelated cleanup found along the way
belongs in its own commit, and usually in its own pull request.

Discuss a substantial change via an issue before making it.

Commit format is in [WRITING.md](WRITING.md#commits).

## Decorum

- Participants will be tolerant of opposing views.
- Participants must ensure that their language and actions are free of
  personal attacks and disparaging personal remarks.
- When interpreting the words and actions of others, participants
  should always assume good intentions.
- Behaviour which can be reasonably considered harassment will not be
  tolerated.

Based on
[Ruby's Community Conduct Guideline](https://www.ruby-lang.org/en/conduct/).

## Security

Please do not open a public issue for a vulnerability. This repository
has no `SECURITY.md` yet; use GitHub's private vulnerability reporting
(the repository's Security tab → "Report a vulnerability") instead of a
public issue or pull request.
