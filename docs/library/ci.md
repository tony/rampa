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
3. Writes JSON output with `--out`
4. Uploads the JSON result as an artifact
5. Writes a markdown comparison summary to `$GITHUB_STEP_SUMMARY`
6. Keeps the artifact available for future baseline comparisons
7. Fails the step if thresholds breach (configurable)

The uploaded JSON artifact is the durable CI record. Add CSV or remote
outputs from {ref}`outputs` if the same run also needs spreadsheet import,
time-series dashboards, OTEL export, or custom ingestion.

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

## GitHub Actions presentation

The GitHub Actions presentation surface is separate from metric storage.
Use it for workflow feedback, and keep JSON/CSV or a remote output enabled
when results must survive beyond the job log. In GitHub Actions
(`GITHUB_ACTIONS=true`), this surface emits:

- `::error::` annotations for failed thresholds
- A markdown summary to `$GITHUB_STEP_SUMMARY`
