(development)=

# Development

Contributing to rampa and understanding its internals.

## Setup

```console
$ git clone https://github.com/tony/rampa.git
```

```console
$ cd rampa && uv sync --all-extras --all-groups
```

## Quality gates

Run before every commit:

```console
$ rm -rf docs/_build; uv run ruff check . --fix --show-fixes; \
  uv run ruff format .; uv run ty check; \
  uv run py.test --reruns 0 -vvv; just build-docs;
```

## Test suite

```console
$ uv run pytest
```

Continuous testing with pytest-watcher:

```console
$ uv run ptw .
```

## Architecture

```text
User script (@scenario)
        │
    Loader ──→ TestPlan
        │
    Engine ──→ RunController
      │  │         │
      │  │     EventBus ──→ CLI / MCP / pytest / JSONL
      │  │
      │  └──→ Executors (6 types)
      │            │
      │        Workers ──→ HttpClient ──→ target
      │            │
      └──→ MetricEngine (thread)
               │
           SinkProtocol ──→ Thresholds ──→ exit code
```

The engine is headless — it owns execution and cleanup. Frontends
own presentation, format, and exit behavior. The `EventBus`
broadcasts typed events to concurrent subscribers.

The metric engine runs in a dedicated `threading.Thread`, draining
samples from a `queue.SimpleQueue` on a 50ms timer. The
`SinkProtocol` is a structural protocol (not ABC) designed as the
future Rust/PyO3 seam.

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item-card} Benchmarks
:link: benchmark
:link-type: doc
Throughput, scheduling, metric engine, and HTTP benchmarks.
:::

:::{grid-item-card} Rust expansion
:link: rust-expansion
:link-type: doc
Optional Rust acceleration via PyO3 — architecture, components, fallback.
:::

:::{grid-item-card} ADRs
:link: ../adrs/index
:link-type: doc
Architecture decision records — significant design choices and rationale.
:::

::::

```{toctree}
:hidden:

benchmark
rust-expansion
../adrs/index
```
