# AGENTS.md

rampa is an async Python load-testing framework: a headless engine,
typed metrics, threshold policies, and six executor types matching
k6's scheduling models, with an optional Rust accelerator.

Follow the conventions already in the tree, and keep a change scoped to
what was asked for.

## What is here

| Path | What it is |
| ---- | ---------- |
| `src/rampa/` | Package source: engine, executors, metrics, HTTP client, CLI, MCP server, pytest/unittest plugins |
| `rust/` | Optional Rust accelerator (`rampa._core`), built with `maturin` |
| `tests/` | Test suite, including the Markdown doc-example harness |
| `docs/` | Sphinx/MyST documentation site (`docs/conf.py`) |
| `docs/adrs/` | Architecture decision records for native-boundary and self-measurement policy |
| `scripts/` | Benchmark scripts and the agent-CLI MCP config swapper |
| `CHANGES` | Changelog, rendered as the docs history page |

## Which policy applies

- Documentation, user-facing text, `CHANGES`, release notes, commit
  messages, docstrings, and source comments:
  [.github/WRITING.md](.github/WRITING.md)
- Environment, the gates, tests, documentation builds, releases, and
  pull requests: [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)

Each of those is the single home for its subject. Where a rule seems to
be stated twice, the file listed above is the one that governs.

## Change discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, helper, API, or test before adding a new one;
  keep a new API private until a caller outside the module needs it.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized module — not for a
  single-use helper or a one-line re-export.
- Add a test for every user-visible behaviour change, and a `CHANGES`
  entry for every change to the public API, CLI, configuration, or
  output.
- A passing gate is evidence only once it has been shown capable of
  failing. Pair a new test with a deliberate break that proves it
  bites.

Rust is an optional accelerator, never a required one: the package
imports, installs, and passes its tests without it, and it exposes no
public API or duck-typing contract the pure-Python implementation
doesn't already define. It must never change what a load test
measures — timing, scheduling, cancellation, or aggregation semantics.
The boundary shapes and the self-harness/benchmark/profile
requirements that enforce this are ADRs 001-006 in `docs/adrs/`; read
those before writing or reviewing native code.

## References

- Changelog: [CHANGES](CHANGES)
- Docs: <https://rampa.git-pull.com/>
- Source: <https://github.com/tony/rampa>
- Architecture decision records: [docs/adrs/index.md](docs/adrs/index.md)
- Inspired by [k6](https://k6.io/)
