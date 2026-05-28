# ADR 002: Native Boundary / Execution Engine Architecture

Status: Proposed
Date: 2026-05-28

## Context

rampa is a Python-first load testing framework. Python is the public API, the
scenario-authoring surface, and the semantic source of truth. Native code (Rust) is an
optional accelerator that must never become required to install, import, or run the package.

ADR 001 governs one shape of native code: a drop-in accelerator that replaces a public
Python callable while preserving its observable behavior, on the PEP 399 model. That model
is correct but narrow. A load tester invites native code in shapes ADR 001 never anticipated
— an internal engine that executes a normalized plan Python hands it, and a worker that runs
independently behind a protocol. These are not accelerators: they do not stand in for a
Python callable, they carry different risks, and treating them as drop-ins is the specific
mistake this ADR prevents.

This ADR is deliberately conservative. The common outcome of native-code ambition in a
Python project is not a faster product but a heavier one — a larger wheel matrix, a build
that breaks on someone's platform, a second implementation that drifts, and a public surface
that quietly forks into "what Python can do" and "what the fast path can do." A portable,
predictable, all-Python load tester that is honest about its ceiling beats a faster one that
is harder to install and trust. Native code is an exception to argue for, not a roadmap.

Two facts about *this* domain shape every rule below.

First, a load generator's per-request path spends most of its time waiting on I/O;
concurrency comes from overlapping that waiting, and the interpreter lock is released across
the wait. So the reflex "load testing is CPU-intensive, rewrite it in Rust" is usually wrong.
CPU cost is real but concentrated — serialization and parsing, TLS, metric aggregation under
high sample rates, scheduling under high arrival rates — and the right response is to profile
and target *that* hotspot, not to nativize the request loop on faith.

Second, scenarios are arbitrary user code. What makes rampa a programmable load tester rather
than a config-file runner is that a scenario can call any Python it wants. Native code that
wants to run inside the per-request loop collides with that: it either calls back into user
Python on every request (reintroducing the boundary cost it went native to escape) or it
refuses to run user Python (so it is no longer running the user's scenario). There is no free
"native execution of arbitrary scenarios." That constraint governs the worker shape below.

This is a policy record. It authorizes future native work and amends ADR 001. It does not
describe, audit, or reconcile any current implementation, and it assumes no current type,
sink, schedule mechanism, protocol struct, or dependency is stable. Every rule below should
remain correct if every line of rampa's native code were deleted and rewritten.

## Decision

rampa adopts a **default of no native code**, and a cost-ordered ladder of three integration
shapes for the exceptions: **accelerator**, **engine**, **worker**. Each native boundary is
assigned to exactly one shape before code is written; the shape fixes the boundary rules, the
test obligations, and which ADR governs it.

### Default rule: no native code until a profile proves otherwise

This is the rule that keeps the other rules from being used. Native code is not added because
a path *might* be hot, because Rust is *available*, or because a microbenchmark of a function
in isolation looks good. It is added only after a profile of the **user-visible path** — the
latency or throughput a user actually observes — shows a CPU bottleneck that the Python
implementation cannot resolve algorithmically or structurally, against a named baseline (trunk
for development; a tag or release for release-facing claims). "It feels slow" is not a profile.
If you cannot point to that profile, the answer is no. This default outranks every shape below:
the shapes describe *how* to integrate native code once the default is overcome, not
*whether* to.

### Accelerator — drop-in for a public Python callable (governed by ADR 001)

An accelerator replaces a pure Python callable with a native one that preserves the public API
and observable behavior exactly. Python defines the meaning; the native version makes that same
meaning faster.

> **Test:** removing the native build changes nothing a user can observe except speed — same
> callable, argument forms, return shapes, exceptions, ordering, equality, hashing.

- **Boundary:** a public Python callable ⇄ its native equivalent. It may be called per item
  (that is what an accelerator is *for*); its per-call cost is justified by the profile the
  default rule already requires.
- **Tests:** the same behavioral suite passes on both paths, with no tolerance (ADR 001).
- Do not dress a simple accelerator up as an "engine" to dodge ADR 001's compatibility tests.

Shape exemplars: orjson, fastuuid, pyxirr.

### Engine — in-process, over a plan or batch

An engine consumes a normalized, typed plan or batch that Python builds, runs synchronously to
completion without holding the interpreter lock, and returns a compact result. Python remains
the authoring surface and source of truth; the native side never sees an arbitrary Python
object graph and never calls back into Python inside a per-item loop.

> **Test:** the boundary is crossed once per coarse unit (per run, per scenario, per batch),
> and the native side returns control to Python on completion.

- **Boundary:** Python-owned normalization ⇄ native-owned plan/batch execution, in-process.
- **Tests:** semantic agreement with the Python path where behavior overlaps — **within a
  documented tolerance** if the engine is intentionally approximate, since a batched reduction
  need not be bit-identical to the scalar Python path — plus plan-normalization, error-mapping,
  and cleanup tests. Behavior with no Python equivalent (internal boundary, lifecycle, or
  failure handling — never new public semantics) gets native-specific tests; the tolerance and
  any narrower feature set are documented.

Shape exemplars: Polars (Python builds a lazy plan; a native engine executes it), pydantic-core
(Python builds a schema; a native core executes it).

### Worker — independent, behind a message-passing protocol (highest bar; ships under its own ADR)

A worker runs **independently** of the Python caller and communicates **by message passing** —
a protocol or channel — rather than by synchronous in-process calls. The distinguishing axis is
message-passing vs. FFI, not the operating-system process: a separate binary, a separate
process, *or* a long-lived native background thread that talks to Python over a channel are all
workers. It runs its own lifecycle and is appropriate for high-scale traffic generation, failure
isolation, or native networking internals.

> **Test:** the boundary is message-passing (channel, socket, pipe) and the native side runs
> its own lifecycle/event loop — the two sides could be versioned, deployed, or replaced
> independently as long as they agree on the protocol.

- **Boundary:** an independent worker ⇄ Python orchestrator, over a versioned protocol.
- **Tests:** protocol schema/contract tests, crash/timeout/cancellation lifecycle tests, and
  equivalence tests against the Python runtime where behavior overlaps. A worker crash is
  reported as an operation failure, never masked by a silent switch to another execution model.

**This ADR authorizes the *shape*, not any particular worker or execution mode.** Introducing a
worker **execution mode and its protocol** requires a follow-up ADR that fixes the protocol,
the feature boundary, the packaging shape, the failure behavior, and the test contract. Once
that mode and protocol exist, additional workers implementing the same protocol are ordinary
feature PRs, not new ADRs. ADR 002 says where the boundary belongs and under what rules; it
does not green-light a rewrite of the request loop. Shape exemplars: ruff, ty, uv — pure-native
workspaces whose boundary to the world is a process boundary, not FFI.

The extra gate exists because of the declarative-subset constraint:

> A worker cannot run arbitrary user Python in its hot loop without reintroducing the boundary
> cost it exists to avoid. So a worker runs a **declarative scenario subset** — targets, rates,
> ramps, and checks drawn from a fixed vocabulary — not arbitrary Python. That is not a faster
> way to run rampa scenarios; it is a second, smaller authoring language living inside the same
> product.

Offering a "native execution mode" is therefore a *product fork*, not a performance toggle. It
must never be the default or a silent fallback. The declarative subset is a consequence of
*today's* FFI constraints, **not an eternal law**: a future ADR may widen it — an embedded
interpreter, a compiled scenario subset, or a measured callback bridge — with its own benchmark
and bridging-cost analysis. Until a measured throughput ceiling blocks a real use case, prefer
to have no native execution mode at all.

### Choosing the shape

Classify the **boundary**, not the component. A component with a single boundary takes the
**narrowest shape that honestly fits** it — never a more powerful shape for headroom, never a
cheaper shape to dodge obligations. "Honest" means the boundary genuinely takes that shape, not
that you wish it did. Evaluate in order and stop at the first that truthfully matches:

1. Replaces a public Python callable, observable only as speed? → **accelerator** (ADR 001).
2. Runs in-process over a typed plan/batch Python built, returning on completion, no per-item
   callbacks? → **engine**.
3. Runs independently behind a message-passing protocol/channel? → **worker** (own ADR).

A component that exposes **more than one boundary** — for example a public callable backed by a
background worker — must satisfy the requirements of **every** shape it touches: each boundary
is governed by its own shape, so the callable surface still answers to ADR 001 *and* the worker
surface answers to the worker rules. It is not enough to satisfy only the strictest. When a
*single* boundary is genuinely ambiguous between two adjacent shapes, take the **stricter
(higher)** one — a true accelerator/engine straddle is governed as an engine, a true
engine/worker straddle as a worker — because under-governing native code (drift, breakage, a
hidden lifecycle) costs more than a few extra checks. Ambiguity is never license to round
*down* to the cheaper rung. A boundary that fits none of the three is not designed yet: design
it before writing native code.

## The boundary is the design

Design the boundary before writing native code. For an **engine or worker** boundary the shape
is wrong if it is crossed per request, per event, per sample, or per node; move it up to a plan,
batch, buffer, or protocol message. (An accelerator is the exception: it is a per-call drop-in
by nature, and its per-call cost is justified by the default rule's profile.) Equally, native
code must not call back into Python inside a per-item loop.

Avoid the per-item engine/worker shape:

```text
Python per-request loop
  -> native: record one sample
  -> native: compute next delay
  -> native: update one threshold
```

Prefer the coarse-unit shape:

```text
Python scenario / config
  -> normalized plan, batch, or protocol message
  -> native work over the coarse unit (no per-item callback, interpreter lock released)
  -> compact result returns to Python
```

During heavy native work that touches no Python objects, release the interpreter lock so other
Python threads make progress. This policy is about the behavior — heavy native work yields the
interpreter — not a particular API spelling, which a clean rebuild chooses at implementation
time. Native errors become Python exceptions or explicit operation failures; native panics,
crashes, and protocol mismatches never silently become a different execution mode.

## Keep user code in the host language

Arbitrary user scenarios run in the Python runtime — the one place a user's full scenario
(branching, custom validation, custom metric hooks, arbitrary callbacks) is guaranteed to run
with full semantics. A native execution mode runs a **declarative scenario subset** only, for
the boundary reason above, not as a judgment about user code. It is explicit, opt-in, never a
silent fallback, and never the default; the line on what it can run is revisitable by a future
ADR (see the worker shape). Until then, native execution does not call user Python in its inner
loop.

## Separate logic from binding

Native logic and the mechanism that exposes it to Python are different concerns. Keep native
logic in a core with **no Python-binding dependency**; expose it through a thin, separate
binding for in-process use (accelerators and engines) and, where applicable, through a separate
worker for message-passing use. One body of logic can then be reached through more than one
boundary without entangling it with any single binding. This is the dominant ecosystem shape —
a binding-free core plus a thin binding; pure-native workspaces compiled to binaries. rampa
adopts the *principle* — binding-free core, thin binding, separate worker — **without committing
to any particular crate count or directory shape**, which a clean rebuild may choose freely.

## Packaging

Keep **one package** while native code is in-process and optional. The base must install,
import, and run on a machine with no native toolchain and no compatible native wheel; missing
native code may remove acceleration, but never the Python API or the ability to run (inherited
from ADR 001, non-negotiable).

A worker reached over a process boundary may be packaged as a separate artifact, since it is a
different build target than an imported extension — though shipping it inside the main package
is preferred while a single distribution remains practical. Do **not** split the project into
separate API and native distributions by default; split only on a documented trigger —
sustained wheel-matrix or build-maintenance pain a single distribution can no longer carry,
recorded when it happens. A stable ABI is an option to *shrink* the wheel matrix when that pain
appears, not a default to adopt preemptively.

## Testing and benchmarks

Test obligations follow the shape (see each shape's *Tests* line above). Across all shapes:
justify native code with a benchmark of the **user-visible path** against a named baseline, not
a microbenchmark of the native function alone, and make the boundary-crossing count visible —
crossing frequency is the metric this ADR cares about most. Native tests never replace the
Python-only suite; a green native job does not compensate for a broken Python-only job.

## Consequences

### Positive

- The default answer to "should this be native?" is no, keeping the base portable, installable
  everywhere, and cheap to reason about.
- When native code appears, its shape, boundary, crossing frequency, and burden of proof are
  fixed before review.
- The boundary sits at plans, batches, and protocols, so native speedups are not eaten by
  per-item crossing cost.
- The native-execution decision surfaces as a product fork under its own ADR, not a hidden flag.
- One body of native logic can be reached through more than one boundary, because logic is kept
  separate from binding.

### Tradeoffs

- The project maintains plan and protocol types alongside the public API, and tolerance-based
  tests for approximate engines.
- A user who needs throughput beyond a single Python process must wait for a worker mode that
  ships under its own ADR, and accept a declarative scenario subset.
- More test surfaces exist than pure Python alone would require.

### Risks

- **Shape inflation** (a simple accelerator dressed up as an "engine" to skip ADR 001) —
  mitigated by ordered, boundary-based assignment that checks the accelerator shape first and
  never rounds down.
- **Hidden lifecycle** (a callable that quietly spawns a background worker) — mitigated by the
  rule that each boundary is governed by its own shape and must satisfy all of them.
- **Silent native execution** — mitigated by explicit, opt-in native modes; worker crashes are
  failures, never fallbacks.
- **Boundary creep** and **premature distribution splits** — mitigated by the native change
  record's crossing-frequency field and the documented-trigger packaging rule.

## Relationship to ADR 001

ADR 001 governs drop-in accelerators; it continues to apply to any native component exposed as a
transparent replacement for a public Python callable. Engines and workers are governed by this
ADR and are not held to ADR 001's exact-match model — but they remain Python-first: Python owns
the public authoring surface, Python-only operation must keep working, and native tests never
replace the Python-only suite. ADR 001 is amended to state this scope.

## Native change record

A pull request that adds or changes native code includes this record (it replaces a long
checklist; a reviewer rejects the change if any field is missing, the shape is too weak for the
boundary, or the profile does not justify native code):

```text
integration shape:       accelerator | engine | worker
user-visible behavior:   what this affects
boundary:                callable | plan/batch | message-passing (process/binary/thread)
crossing frequency:      per item (accelerator, benchmark-justified) | per run | per scenario |
                         per batch | per protocol message
user Python in hot loop: no | bridged (cite approving ADR)
profile + baseline:      user-visible-path profile + named baseline that justify this
interpreter lock:        released during heavy native work? where?
tests:                   Python-vs-native comparison (identity accelerator / tolerance engine /
                         protocol+crash worker)
python-only preserved:   base installs, imports, runs, and passes its suite without native code
packaging impact:        none | worker artifact (+ reason)
```

For a worker, the record also names the follow-up ADR that defines its protocol and
execution-mode boundary.

## Final position

The most useful native-code policy for a Python-first load tester is one that is hard to invoke.
rampa stays all-Python by default, proves the bottleneck on the user-visible path before writing
any native code, puts the boundary at plans and protocols rather than per-request calls, and
treats a native execution mode as a product fork that ships under its own ADR — not an engine
flag. Native code may make rampa faster. It must not make rampa less Pythonic, less portable,
less tested, less predictable, or quietly split into two languages.
