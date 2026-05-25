(cli-run)=

# rampa run

Execute a load test script.

```console
$ rampa run load_test.py
```

## Command

```{eval-rst}
.. argparse::
   :module: rampa.cli
   :func: build_docs_parser
   :prog: rampa
   :path: run
   :nodescription:
```

## Examples

Run with 20 VUs for 1 minute:

```console
$ rampa run load_test.py --vus 20 --duration 1m
```

Run a specific scenario:

```console
$ rampa run load_test.py --scenario smoke
```

Save results as JSON:

```console
$ rampa run load_test.py --out results.json --quiet
```

Capture the event stream for postmortem analysis:

```console
$ rampa run load_test.py --event-log events.jsonl
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All thresholds passed |
| 1 | Threshold breach |
| 2 | Iteration exception |
| 3 | Invalid configuration |
| 4 | Aborted (SIGINT) |
| 5 | Setup failure |
| 6 | Output failure |
| 7 | Teardown failure |
