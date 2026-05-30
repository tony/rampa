# Cross-cutting: metric & percentile data structures

The metric/percentile structure is the one CPU hot path in a load generator that is *not* I/O-bound,
and it is the part that must survive both very long runs (memory) and distribution (merge). Every tool
converges on the same shape — a bounded summary, recorded cheaply, reduced after merge — and differs
only on the exact-versus-approximate trade-off.

## The structures compared

| Tool | Structure | Memory | Exact? | Mergeable? | Record cost | Query cost |
|---|---|---|---|---|---|---|
| wrk | direct-indexed histogram (`data[µs]`) | linear in `timeout` | exact (µs) | no (array) | O(1) atomic add | O(limit) scan |
| locust | bucketed dict (`{rounded_ms: count}`), coarser as values grow | bounded | approx (rounding) | **yes** (sum buckets) | O(1) | O(buckets) |
| goose | `BTreeMap<usize,usize>` bucketed, adaptive rounding bands | bounded | approx (rounding), clamped to exact min/max | yes | O(log n) | O(buckets) |
| vegeta | t-digest (compression 100) | constant | approx (~rel. error) | **yes** | O(log n) | O(1)–O(log n) |
| artillery | DDSketch (1% relative accuracy) | bounded | approx (1% rel.) | **yes** (lossless within accuracy) | O(1) | O(1) |
| hey | sorted slice (cap 1M) + 10 fixed buckets | O(n) to cap | exact to cap | no | O(1) append | O(n log n) sort |
| jmeter | `DescriptiveStatistics` window / streaming `PercentileAggregator` | window-bound / spill | exact | no (window) | O(1) add | O(n) |

Source structures: wrk [`src/stats.h`](https://github.com/wg/wrk/blob/4.2.0/src/stats.h) ·
locust [`locust/stats.py`](https://github.com/locustio/locust/blob/2.44.0/locust/stats.py) ·
goose [`src/metrics.rs`](https://github.com/tag1consulting/goose/blob/0.18.1/src/metrics.rs) ·
vegeta [`lib/metrics.go`](https://github.com/tsenart/vegeta/blob/v12.13.0/lib/metrics.go) ·
artillery [`packages/core/lib/ssms.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/core/lib/ssms.js) ·
hey [`requester/report.go`](https://github.com/rakyll/hey/blob/v0.1.5/requester/report.go) ·
jmeter [`report/processor/PercentileAggregator.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/report/processor/PercentileAggregator.java).

## The invariants every tool obeys

1. **Bounded summary, not raw samples.** Only hey retains raw latencies (and caps them at 1M);
   everyone else records into a fixed/bounded structure so memory is independent of run length.
2. **Record is O(1) and off-contention.** wrk uses lock-free atomic increments; vegeta/hey/goose feed
   a single consumer; the reduction never sits behind a per-request mutex.
3. **Reduce after merge — never average percentiles.** locust sums histogram buckets, artillery
   merges DDSketches, vegeta merges t-digests, then computes the percentile on the combined summary.
   Averaging two precomputed p99s is the bug this structure exists to prevent.
4. **Exact vs approximate is a deliberate, documented choice.** Single-process tools can stay exact
   (wrk direct-index; hey sort). Distributed tools must use a *mergeable* summary
   (histogram/t-digest/DDSketch) and accept a documented tolerance — because exact distributed
   percentiles would require shipping every raw sample.

The split maps directly onto the boundary taxonomy: a metric reducer over a batch is the canonical
in-process engine, and the mergeable-summary requirement is exactly why a histogram/sketch is
justified at the distributed merge point even when an exact sort would do in one process.
