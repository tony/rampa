(cli-check)=

# rampa check

Validate a test script without running it. Discovers scenarios,
validates executor configurations, and reports a summary.

```console
$ rampa check load_test.py
```

## Command

```{eval-rst}
.. argparse::
   :module: rampa.cli
   :func: build_docs_parser
   :prog: rampa
   :path: check
   :nodescription:
```

## Example output

```text
scenarios: 2 found
  - smoke (constant-vus, 5 VUs, 10s)
  - load (ramping-vus)
thresholds: 2 configured
setup: yes
teardown: no
status: valid
```

## What it checks

- Script imports and loads without errors
- {func}`~rampa.loader.scenario` decorators are discovered
- Executor names are valid (with fuzzy suggestions for typos)
- Setup and teardown functions are detected
- Threshold expressions are listed

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Script is valid |
| 1 | Validation error (no scenarios, bad executor, import failure) |
| 2 | File not found |
