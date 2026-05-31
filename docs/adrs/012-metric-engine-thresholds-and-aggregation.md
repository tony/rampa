# ADR 012: Metric Engine, Thresholds, and Aggregation

Status: Proposed
Date: 2026-05-31

## Context

ADR 009 produces operation attempts. ADR 010 produces scheduler events. ADR 011 produces protocol
and adapter measurements. rampa needs one metric engine that can summarize all of them locally and
merge worker summaries later.

The load-tester research is consistent: raw samples are useful for local diagnosis, but distributed
systems need bounded, mergeable summaries. The caution from distributed-load-testing systems is just
as clear: averaging precomputed percentile fields gives wrong answers. Percentiles must be computed
after summaries are merged.

## Decision

rampa stores metrics as typed observations projected into bounded summaries. Summaries are
mergeable by metric name, unit, bounded tags, run id, scenario id, operation id, segment id, worker
id, region or pool when present, and run-relative period. Thresholds evaluate on the merged summary
view, never on averaged worker percentiles.

The metric engine has three paths:

- hot-path observation ingestion;
- periodic summary snapshots for live output;
- final merged summaries for thresholds and reports.

Raw observations are not retained by default. Debug retention is bounded and separate from the
summary path.

## Metric Types and Namespaces

The initial metric types are:

| Type | Use |
|---|---|
| counter | Counts events such as started, completed, failed, dropped |
| gauge | Last or current value such as active VUs |
| trend | Duration or size distributions |
| rate | Derived ratio over a declared numerator and denominator |

Primary namespaces are:

| Namespace | Examples |
|---|---|
| `iterations.*` | `started`, `completed`, `dropped`, `late` |
| `checks.*` | `passed`, `failed` |
| `http.*` | `duration`, `failed`, `bytes_in`, `bytes_out` |
| `browser.*` | `first_paint`, `first_contentful_paint`, `operation_duration` |
| `bench.*` | `wall_time`, `cpu_time`, `exit_code`, `memory_peak`, `call_count` |
| `adapter.*` | adapter startup, crash, timeout, and protocol counters |

Metric definitions declare unit, type, allowed tags, and merge behavior. Foreign metric names are
import aliases, not the documented primary names. Enterprise-scale dimensions such as worker,
segment, region, pool, environment, and adapter are metadata dimensions on summaries, not separate
metric namespaces.

## Summary Structures

Counters and gauges merge by arithmetic rules appropriate to their type. Trend metrics use a
bounded mergeable distribution: histogram, t-digest, or DDSketch-style sketch. The exact structure
may vary by metric family, but the public contract is fixed:

```text
record cheaply
bound memory
merge summaries
compute percentiles after merge
declare approximation tolerance when approximate
```

Exact local samples may be retained for small diagnostic runs, but they are not the distributed
wire format.

## Thresholds

Thresholds are policy over aggregate metrics:

```python
rampa.metric("http.duration").p(95) < rampa.ms(500)
rampa.metric("http.failed").rate < 0.01
rampa.metric("iterations.dropped").count == 0
```

A threshold expression records:

```text
metric selector
tag filters
aggregation function
window or final scope
comparison operator
expected value and unit
```

Rates require an explicit denominator. For example, an HTTP failure rate is failed attempts divided
by total HTTP attempts in the same selector and window. A check failure rate is failed checks divided
by total checks. rampa does not infer denominators from metric names alone.

## Distributed Aggregation

Workers emit summaries, not raw observations, by run-relative period. The coordinator merges
compatible summaries and then computes percentiles, rates, and thresholds. Worker-level percentile
fields may be displayed as worker diagnostics, but they are not averaged into final results.

Stragglers are explicit. A period can be finalized when all expected workers report or when the
driver's timeout policy closes the period with missing-worker diagnostics. Late summaries remain
mergeable into final results when the run policy allows them.

## Consequences

### Positive

- Metrics can support HTTP, browser, benchmark, and adapter work without separate report engines.
- Distribution has a correct aggregation path from the start.
- Thresholds become stable pass/fail policy rather than report formatting.
- Memory stays bounded during long runs.

### Tradeoffs

- Approximate trend summaries require documented tolerances.
- Rate metrics need explicit denominator definitions.
- Raw sample analysis requires opt-in diagnostics.

## Relationship to Other ADRs

ADR 009 supplies attempts and failure classes. ADR 010 supplies scheduler counters. ADR 011 supplies
protocol and adapter metric observations. ADR 013 transports summaries across workers. ADR 014 and
ADR 015 add browser and benchmark namespaces that this metric engine must keep distinct from HTTP
load-test metrics.

## Final Position

rampa computes truth from mergeable summaries. Raw samples and worker percentiles are diagnostics;
final percentiles and thresholds are computed only after compatible summaries are merged.
