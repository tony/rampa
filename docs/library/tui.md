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

Use the console summary when you only need final results:

```console
$ rampa run load_test.py
```

Use progress output when you want a single live status line on stderr:

```console
$ rampa run load_test.py --progress
```

Use the TUI when you want a full interactive dashboard:

```console
$ rampa run load_test.py --tui
```

The `--progress` flag requires no additional dependencies.
The `--tui` flag requires `textual>=3.0` (installed via `rampa[tui]`).
