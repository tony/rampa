(ci)=

# CI integration

rampa integrates with CI pipelines for automated benchmarking and
performance regression detection.

## GitHub Action

Use the built-in composite action:

```yaml
- uses: tony/rampa/.github/actions/rampa-benchmark@main
  with:
    script: tests/load_test.py
    vus: 10
    duration: 30s
```

The action:
1. Installs rampa
2. Runs the load test
3. Uploads results as an artifact
4. Writes a markdown summary to `$GITHUB_STEP_SUMMARY`
5. Fails the step if thresholds breach (configurable)

## Result comparison

Compare two result files from the CLI:

```console
$ python -m rampa.ci.compare \
  --baseline baseline.json \
  --current current.json \
  --format markdown
```

Output formats: `text`, `markdown` (for PR comments), `json`.

Metrics with >5% degradation are flagged as regressions.

## GitHub Actions output backend

Add the `github` output backend to emit threshold annotations:

```console
$ rampa run load_test.py --output github
```

When running in GitHub Actions (`GITHUB_ACTIONS=true`), this emits:
- `::error::` annotations for failed thresholds
- A markdown summary to `$GITHUB_STEP_SUMMARY`
