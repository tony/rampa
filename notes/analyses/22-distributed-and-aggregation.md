# Cross-cutting: distributed execution & aggregation

When one box saturates, a load generator either ships aggregated summaries to a coordinator or stays
single-process and leaves fan-out to the operator. The tools that distribute all obey the same rules;
the ones that don't make a deliberate library-first choice.

## Who distributes, and how

| Tool | Model | Transport / wire | What crosses | Coordinator role |
|---|---|---|---|---|
| locust | master/worker | ZeroMQ ROUTER/DEALER + msgpack `Message(type,data,node_id)` | aggregated stats every ~3 s | merges histograms; runs no users |
| jmeter | master/worker | RMI `RemoteSampleListener` | `SampleResult`s (volume tuned by `SampleSender`) | aggregates all samples (bottleneck) |
| artillery | launcher/workers | worker_threads locally; SQS/queue on Lambda/Fargate | DDSketch periods (timestamp-bucketed) | merges periods, timeout-bounded |
| k6 | single-process local runner | outputs/cloud adapters consume sample batches | samples or output-specific buckets | none locally |
| vegeta | single-process | — (Unix pipes between stages) | — | none |
| hey | single-process | — | — | none |
| wrk | single-process | — | — | none |
| goose | single-process | — | — | none |

Source: locust [`locust/rpc/protocol.py`](https://github.com/locustio/locust/blob/2.44.0/locust/rpc/protocol.py) ·
jmeter [`samplers/RemoteSampleListener.java`](https://github.com/apache/jmeter/blob/rel/v5.6.3/src/core/src/main/java/org/apache/jmeter/samplers/RemoteSampleListener.java) ·
artillery [`platform/local/worker.js`](https://github.com/artilleryio/artillery/blob/artillery-2.0.32/packages/artillery/lib/platform/local/worker.js) ·
k6 [`output/types.go`](https://github.com/grafana/k6/blob/v2.0.0/output/types.go).

## The rules the distributing tools share

1. **Ship summaries, not raw events.** locust sends periodic aggregated stats; jmeter offers
   `Batch`, `Asynch`, `DiskStore`, `Statistical`, and `DataStripping` senders precisely because
   per-sample RMI swamps the controller; artillery ships DDSketch periods. Per-request events
   across the wire is the anti-pattern.
2. **Reduce after merge.** The coordinator combines mergeable summaries (sum histograms / merge
   sketches) and computes percentiles on the result — see [`21`](21-metric-data-structures.md). This is
   why distribution *requires* a mergeable metric structure.
3. **The coordinator is the scaling ceiling.** It runs no load (locust) or becomes the bottleneck if
   it must process every sample (jmeter). Keeping it cheap — merge-only, batched, summary-level — is
   the lever.
4. **Tolerate stragglers explicitly.** artillery's launcher buffers periods by timestamp and emits a
   merged period once all workers report *or* after a timeout, so a slow/dead worker degrades liveness,
   not correctness. Mergeable summaries make a late period still combinable.

## The single-process choice

k6's local runner, vegeta, hey, wrk, and goose deliberately do not build distribution in: they are
library-first or single-binary, reach high per-box throughput (open-loop goroutines / sharded
reactors / tokio tasks), and leave fan-out to the operator (shell, orchestrator, cloud service, or a
wrapping program). The trade is simplicity and a clean library boundary against turnkey fleet scale.
