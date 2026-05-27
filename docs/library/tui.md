(tui)=

# TUI dashboard

rampa includes a live terminal dashboard for real-time monitoring
during load tests.

## Installation

```console
$ pip install rampa[tui]
```

## Usage

```console
$ rampa run load_test.py --tui
```

The dashboard shows:

- **Phase indicator** — setup, executing, paused, teardown, complete
- **Execution metrics** — VU count, iteration count/rate, error count, duration
- **HTTP timing** — request count/rate, p50/p90/p95/p99 latency
- **Threshold status** — pass/fail for each configured threshold

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Pause / Resume |
| `s` | Stop test |

## Progressive display options

rampa offers three levels of live output:

```console
$ rampa run load_test.py                # Console summary after completion
```

```console
$ rampa run load_test.py --progress     # Single-line live status on stderr
```

```console
$ rampa run load_test.py --tui          # Full interactive dashboard
```

The `--progress` flag requires no additional dependencies.
The `--tui` flag requires `textual>=3.0` (installed via `rampa[tui]`).
