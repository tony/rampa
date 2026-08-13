# Load-tester structural analyses

Structural analysis of how production load generators are built — their execution engines,
scheduling models, request/result data structures, metric/percentile data structures, and
distributed aggregation. These are research notes (not product docs); they inform rampa's
direction but decide nothing.

## Method

1. **Portable citations first.** Every external reference is a **deep link to a specific file
   pinned at a git tag** — never `main`/`master`/`HEAD` or a bare SHA. These public links are the
   reproducible source surface for the analysis.
2. **Source review second.** Confirm and deepen against checked-out source using `rg`/`ag`/`fd`.
   Private local notes may inform drafting, but tracked notes should not require workstation paths
   to read or verify.

## Tools and pinned versions

| Tool | Repo | Tag |
|---|---|---|
| locust | `locustio/locust` | `2.44.0` |
| jmeter | `apache/jmeter` | `rel/v5.6.3` |
| k6 | `grafana/k6` | `v2.0.0` |
| vegeta | `tsenart/vegeta` | `v12.13.0` |
| hey | `rakyll/hey` | `v0.1.5` |
| wrk | `wg/wrk` | `4.2.0` |
| artillery | `artilleryio/artillery` | `artillery-2.0.32` |
| goose | `tag1consulting/goose` | `0.18.1` |

## Files

- [`00-taxonomy.md`](00-taxonomy.md) — the types of load testers, as a classification matrix.
- Per-tool structural docs: [`10-locust.md`](10-locust.md), [`11-jmeter.md`](11-jmeter.md),
  [`12-vegeta.md`](12-vegeta.md), [`13-hey.md`](13-hey.md), [`14-wrk.md`](14-wrk.md),
  [`15-artillery.md`](15-artillery.md), [`16-goose.md`](16-goose.md), [`17-k6.md`](17-k6.md).
- Cross-cutting: [`20-engines-and-scheduling.md`](20-engines-and-scheduling.md),
  [`21-metric-data-structures.md`](21-metric-data-structures.md),
  [`22-distributed-and-aggregation.md`](22-distributed-and-aggregation.md),
  [`23-control-plane-and-execution-drivers.md`](23-control-plane-and-execution-drivers.md).

Each per-tool doc follows the same section order (classification · execution engine · scheduling &
pacing · result data structure · metric data structure · distributed/aggregation · scenario API ·
atlas reference) so the tools are directly comparable.
