(cli-inspect)=

# rampa inspect

Inspect a test script without running it. Use this when you want to see
resolved scenarios, thresholds, lifecycle hooks, and executor values
before starting load generation.

```console
$ rampa inspect load_test.py
```

## Command

```{eval-rst}
.. argparse::
   :module: rampa.cli
   :func: build_docs_parser
   :prog: rampa
   :path: inspect
   :nodescription:
```

## Examples

Show resolved configuration as text:

```console
$ rampa inspect load_test.py
```

Emit JSON for scripts and agents:

```console
$ rampa inspect load_test.py --format json
```
