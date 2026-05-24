# scripts/

Developer utilities shipped with the repo but not part of the installed
package.

## `mcp_swap.py`

Swap the rampa MCP server entry across every detected agent CLI
(Claude Code, Codex, Cursor, Gemini) so all four run the **local checkout**
instead of a pinned PyPI release. Useful when testing a branch or working
on the server itself.

### Usage

From the repo root:

```console
$ uv run scripts/mcp_swap.py detect      # which CLIs are installed?
$ uv run scripts/mcp_swap.py status --server rampa
$ uv run scripts/mcp_swap.py use-local --entry rampa-mcp --dry-run
$ uv run scripts/mcp_swap.py use-local --entry rampa-mcp
$ uv run scripts/mcp_swap.py revert
```

### What `use-local` does

For each detected CLI, the rampa entry is rewritten to:

```
command = "uv"
args    = ["--directory", "<repo-abs-path>", "run", "rampa-mcp"]
```

This takes advantage of `uv run`'s automatic editable install — source
edits flow through on the next invocation with no reinstall step.

### Safety

- Every rewrite writes a timestamped backup before touching the file.
- State is tracked in `~/.local/state/rampa-dev/swap/state.json`
  (honours `XDG_STATE_HOME`) so `revert` knows which backup to restore.
- Writes are atomic (tempfile + `os.replace`) and re-validated.
- `--dry-run` prints a unified diff and writes nothing.

### Scope

Covers four CLIs and their canonical global config paths:

| CLI    | Config                       | Format |
|--------|-------------------------------|--------|
| Claude | `~/.claude.json`              | JSON   |
| Codex  | `~/.codex/config.toml`        | TOML   |
| Cursor | `~/.cursor/mcp.json`          | JSON   |
| Gemini | `~/.gemini/settings.json`     | JSON   |

## Benchmark scripts

See `bench_*.py` for load testing benchmarks:

- `bench_scheduler.py` — Arrival-rate scheduling precision
- `bench_throughput.py` — Maximum iterations/sec
- `bench_metrics.py` — Metric engine ingestion rate
- `bench_http_local.py` — HTTP overhead measurement

All support `--json-output` and `--ndjson` flags for CI integration.
