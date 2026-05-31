# ADR 010: Execution and Scheduling Model

Status: Proposed
Date: 2026-05-31

## Context

ADR 008 exposes typed schedule constructors and fixes the distinction between closed-loop and
open-loop schedules. The load-tester atlas shows why this matters: concurrency controls throughput,
but scheduling controls honesty. Closed-loop virtual users slow down when the target slows.
Open-loop arrival schedules keep offering work and record overload instead of hiding it.

The scheduler therefore owns pacing, virtual-user lifetime, drift accounting, dropped work, and the
scheduled-versus-actual timestamps consumed by ADR 009 and ADR 012.

## Decision

rampa uses two scheduler families under one executor interface:

- closed-loop schedulers, where each VU starts the next iteration after the prior iteration
  completes and any configured wait/pacing has elapsed;
- open-loop schedulers, where iteration starts are driven by a monotonic arrival schedule
  independent of prior completion.

Both families emit scheduled start, actual start, completion, lateness, dropped/overflow, timeout,
and cancellation information into operation attempts and iteration events.

`repeat(n)` is a finite diagnostic schedule that uses the same executor contract without making a
load-shape claim. It exists so smoke checks, profile captures, browser probes, and benchmark
targets can say "run this N times" without choosing a VU or arrival-rate model.

## Closed-Loop Semantics

Closed-loop schedules include `vus`, `ramping_vus`, `per_vu_iterations`, `shared_iterations`, and
the finite `repeat(n)` helper. A VU persists across its iterations. VU-scoped state such as cookies,
auth tokens, protocol sessions, and user data survives until that VU exits.

Once-per-VU initialization is distinct from once-per-run setup. A setup failure prevents that VU
from running and is classified as setup failure; it does not silently become a failed protocol
attempt.

Closed-loop throughput is reported as observed throughput, not offered load. If target latency
increases, fewer iterations complete. Reports must not describe that as a constant arrival rate.

For `repeat(n)`, the default execution is one logical VU running exactly N iterations sequentially.
Reports describe completed attempts and durations, not throughput or offered load. A future
parallel finite schedule must use a separate constructor or an explicit option so examples do not
change meaning.

## Open-Loop Semantics

Open-loop schedules include `arrivals` and `ramping_arrivals`. The scheduler computes a run-relative
monotonic start time for each planned iteration. If the scheduler is late, the actual start records
that lateness. If concurrency capacity is exhausted, rampa records the iteration as dropped rather
than slowing the schedule.

Open-loop iterations may borrow VUs from a pool, but a borrowed VU's mutable state must not leak
between logically independent arrivals unless the plan explicitly opts into a reusable session pool.
The default is isolation for correctness and clear attribution.

Open-loop reports distinguish:

```text
scheduled iterations
started iterations
dropped iterations
late iterations
completed iterations
```

This preserves coordinated-omission visibility under overload.

## Timing Model

Schedulers use monotonic clocks for all measurement. Wall-clock time appears only in run metadata,
logs, and artifact naming. The scheduler records:

```text
scheduled start
actual start
start delay
operation duration
iteration duration
completion time
```

Distributed workers report worker-local run-relative times. Cross-worker live charts require a
start barrier and declared clock-skew tolerance from ADR 013. Final aggregate correctness does not
depend on globally aligned monotonic clocks.

## Cancellation and Timeout

Cancellation is cooperative and explicit. A run stop request prevents new scheduled starts and asks
running attempts to finish or cancel according to the selected policy. Timeout is classified at the
level where it occurs: server startup timeout, scheduler timeout, protocol operation timeout,
adapter timeout, or worker heartbeat timeout.

Schedulers do not convert timeout into a generic error. The failure class is preserved through ADR
009 and ADR 012.

## Consequences

### Positive

- Closed-loop and open-loop reports are honest about what was offered and what completed.
- VU state lifetime is explicit and testable.
- Dropped and late iterations become measurable overload signals.
- Distributed mode can reuse the same run-relative timing model.

### Tradeoffs

- Open-loop isolation is more expensive than implicit VU reuse.
- Reports need more fields than a simple completed-iteration count.
- The scheduler must be tested with injected clocks to avoid flaky timing tests.

## Relationship to Other ADRs

ADR 008 names schedule constructors. ADR 009 records scheduled and actual timing. ADR 012 defines
the metrics derived from scheduler events. ADR 013 partitions schedules across workers and defines
start barriers for distributed runs.

## Final Position

rampa treats scheduling as a measurement feature, not a loop detail. Closed-loop schedules measure
what completed; open-loop schedules measure what was offered, what started, what was late, and what
was dropped.
