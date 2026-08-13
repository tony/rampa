# Cross-cutting: control plane, execution drivers & remote runtime

Distributed engines that long predate load testing — query engines, schedulers, and actor systems —
converge on the same runtime shape: a small stable user contract, work normalized into a plan, a
swappable executor behind one lifecycle, narrow workers that only execute and report, and a separate
read model for status. This note records that shape as a parking lot for the scale-and-control-plane
work deferred to ADR 013; like the rest of `notes/analyses`, it informs direction and decides
nothing.

## The three planes

Serious distributed systems split into a control plane (what runs where), a data plane (workers that
execute), and a read model (status/history that observes without scheduling).

| System | Control plane | Data plane (worker) | Read model |
|---|---|---|---|
| Ballista | scheduler: jobs/stages/tasks, assignment, heartbeats, retries | executor decodes a serialized plan partition, runs the single-node engine, reports status | scheduler REST/status surface |
| Spark | driver: DAG/task scheduling, capacity | executors run task sets | listener/event bus → status store → UI/history server |
| Ray | GCS + per-node raylet scheduling | workers run tasks under a runtime env | dashboard / state API |
| Hadoop YARN | ResourceManager: assignment, capacity | NodeManager containers | RM UI / history server |
| Airflow | scheduler + `BaseExecutor` (Local / Celery / Kubernetes) | workers run task instances | webserver + metadata DB |
| AWS DLT | Step Functions orchestration | Fargate tasks run the load-generator binary | DynamoDB history + live stream + artifact store |

## The recurring rules

1. **One user contract, many drivers.** The executor is swappable behind a stable lifecycle and the
   user-facing API does not change with scale. Airflow's `BaseExecutor` is satisfied identically by a
   subprocess pool, a broker queue, and a pod-per-task backend; Ballista runs in-process (standalone)
   or distributed through the same session entry point. Scale is a driver choice, not a different
   product.
2. **Ship a normalized plan to narrow workers.** The worker decodes a serialized plan or task and
   runs the same single-node engine; it makes no scheduling decisions. The control plane decides
   *where/whether*, the data plane only executes and reports (Ballista, Spark). This is the same
   "ship the plan, not ad-hoc instructions" boundary the user-facing `Plan` already encodes (ADR 008).
3. **The read model observes; it does not schedule.** Status, history, and UIs consume events and
   summaries off the hot path — Spark's listener/event bus feeds a status store that feeds the UI and
   history server, none of which is the scheduler. A future rampa run-store or status API is a read
   model and must stay off the measurement path.
4. **Remote execution is mostly packaging and lifecycle.** What crosses the boundary is a versioned
   code bundle, an environment spec, and artifact references — plus readiness, a start barrier, and
   cleanup. Ray materializes a runtime environment per job; Spark Connect uploads artifacts before
   execution; AWS DLT runs archive → stabilize → start marker → completion markers → stored results.
   Workers must run the *pinned same code and environment*, or merged results compare unlike runs —
   the distributed analog of the rule below.
5. **Aggregate with mergeable metric summaries; never average percentiles.** Workers emit bounded
   summaries keyed by metric, tags, time window, worker, and run; the coordinator merges and then
   computes percentiles. The cautionary counter-example is AWS DLT's results parser, whose
   `createFinalResults` runs per-task percentile fields through an arithmetic mean
   ([`source/results-parser/lib/parser/index.js`](https://github.com/aws-solutions/distributed-load-testing-on-aws/blob/v4.1.0/source/results-parser/lib/parser/index.js)).
   See [`21`](21-metric-data-structures.md) and [`22`](22-distributed-and-aggregation.md).

## The failure model is simpler than a query engine's

Query DAGs (Ballista, Spark) recover by rolling back stages whose shuffle output is lost and the
stages that depend on it — a transitive cascade, because stages feed each other. Load-test work units
are independent: a worker runs its segment and emits summaries that depend on no other worker. A lost
worker loses only its segment's contribution, so the honest response is reassign-the-segment or
tolerate-it-as-a-straggler (artillery's bounded-period model), not transitive rollback. Do not import
query-engine recovery machinery — shuffle materialization, location-based dependency resolution,
cascading retry — that the embarrassingly-parallel load case does not need.

## What this leaves for ADR 013

Deferred constraints for the scale-and-control-plane ADR, not decisions made here: the
control/data/read split; a swappable execution driver behind one streaming, controllable lifecycle;
versioned code bundles, environment specs, and an artifact store as first-class; readiness, start
barrier, and cleanup as explicit lifecycle phases; and a bounded, mergeable summary as the only thing
crossing the wire by default. The biggest anti-pattern the atlas keeps naming: building distributed
mode by shipping raw per-request samples to a central process and reconstructing correct metrics
afterward. The boundaries have to be explicit before scale arrives.

Sources: AWS DLT pinned at `v4.1.0` above. Structural detail for the data-system exemplars (Ballista
scheduler/executor, Spark listener-bus/status-store, Ray GCS/raylet/runtime-env, Hadoop YARN
ResourceManager, Airflow `BaseExecutor`) lives in each project's upstream source; this note records
the cross-cutting pattern, not a line-level dive.
