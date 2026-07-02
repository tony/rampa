# Documentation voice

This file covers the *voice* of prose under `docs/` — how to frame a
page so a reader meets the idea before its API surface. It complements
the repository-root `AGENTS.md`, which already governs code blocks,
shell-command formatting, changelog conventions, and MyST roles. When
the two overlap, the root file wins; this one only answers the
question it leaves open: how should the prose sound?

## Who you are writing for

The default reader writes async Python scenario scripts — an
`@rampa.scenario` function that takes a `Worker` — and runs them with
`rampa run`. They are fluent in load-testing vocabulary — VUs, closed
and open models, arrival rates, percentiles, thresholds, often from
k6 — and comfortable with async Python, but you cannot assume they
know rampa's internals: the headless `Engine` and its run controller,
the metric engine, executor scheduling, output backends, or the
optional Rust accelerator.

A second, smaller reader drives rampa programmatically — the headless
`Engine` from pytest, the TUI, the MCP server, CI comparison — or
works on rampa itself. Serve them too, but mark their material opt-in
("for programmatic use", "advanced") so the default reader knows they
can stop. Never make the common case pay a comprehension tax for the
advanced one.

## Voice

- **Second person, present tense, active.** "You ramp the arrival
  rate", not "The arrival rate is ramped". Address the reader who is
  doing the thing.
- **Concept before API surface.** Open by saying what the thing *is*
  and what it does for the reader. The surface — the decorator kwargs,
  the CLI flags, the threshold grammar — is the last detail they need,
  not the first. A page that opens with a kwarg list has buried the
  idea under its mechanics.
- **Say when they can stop.** Lead with the default and the
  reassurance: `constant-vus` covers most tests, the advanced parts
  are optional. Let a skimmer leave after one paragraph.
- **Grant permission, don't demand attention.** "Reach for this
  when…", "for programmatic use" — tell readers they're in the right
  place without implying they must read on.
- **Progressive disclosure.** Order by how many readers need it: the
  one-decorator scenario → the one kwarg a few will tune → a
  module-level `Config` with several scenarios → driving the headless
  `Engine` yourself. Each step is for a smaller audience than the last.
- **Lean on the pipeline.** The reader thinks scenario → executor →
  `Worker` iterations → metrics → thresholds → exit code; reinforce
  that chain when you explain where a feature sits. It is the mental
  model the whole framework hangs on.
- **Name the trade-off.** If a choice costs something — an open-model
  executor piles up VUs and drops iterations when the target slows —
  say so, and say what it buys ("the rate holds, so you measure the
  target at a load you chose"). State it; don't sell it.
- **Frame by concept, not by mechanism.** Don't headline a feature by
  its kwarg or CLI flag in prose; that names the implementation
  surface, which is the reader's last concern. Name the concept
  ("maintain a fixed request rate", not `pre_allocated_vus`). The
  mechanics vocabulary — a kwarg table, the threshold expression
  grammar, the exit-code table — belongs in a reference table or the
  API docs, and only there.

## Keeping examples honest

Nothing under `docs/` executes: pytest's `testpaths` covers
`src/rampa` and `tests`, so a drifted example fails no build and no
test. Correctness is manual — run every new or changed example
against the current public API before you commit.

- Prefer complete scripts a reader can paste into `load_test.py` and
  run with `rampa run`; a fragment that assumes an invisible import or
  `config` is a support ticket.
- Fence Python as ```` ```python ```` and shell commands as
  ```` ```console ```` at a `$` prompt, per the root `AGENTS.md`.
- Reuse the example hosts already in the docs (`httpbin.org`,
  `api.example.com`) rather than inventing new targets.

## What stays precise

Warm the framing, never the facts. Executor tables, the threshold
expression grammar, metric names (`http_req_duration`,
`dropped_iterations`), exit codes, and class or function
cross-references carry meaning in their exact form — leave them alone.
The friendly voice belongs in the sentences *around* a precise block,
introducing it, not inside it paraphrasing it into vagueness.

## Cross-references

Point the advanced reader at the deep-dive rather than inlining it,
and put the link where their interest peaks — on the phrase that made
them curious ("drive the engine yourself", "compare runs in CI") —
not as a standalone footnote the eye skips. Use the MyST roles listed
in the root `AGENTS.md` (`{class}`, `{meth}`, `{func}`, `{exc}`,
`{attr}`, `{ref}`, `{doc}`). Every page opens with an explicit
`(anchor)=` target in lowercase hyphenated form (`cli-run`,
`api-reference`); a `{ref}` must match its target's anchor exactly.
`just build-docs` catches a broken cross-reference; nothing else does
— so build the docs before you commit.

Link the first prose mention of any symbol that has a useful
destination on that page. This includes Python objects, rampa APIs,
CLI command pages, topic pages, and external tools or projects. Use
the most specific target available: `{class}`, `{meth}`, `{func}`,
`{exc}`, or `{attr}` for API objects; `{ref}` or `{doc}` for
documentation pages and section anchors; and a Markdown link or
reference link for external projects. After the first linked mention
on a page, later mentions can stay plain unless the distance or
context makes another link useful.

Do not rely on a later reference section to satisfy the first-mention
rule. If the first occurrence would be a heading, grid-card teaser, or
introductory sentence, link that occurrence or retitle the heading so
the first prose mention can carry the link. Leave command examples,
code blocks, and literal configuration values as code; link the
surrounding prose instead.

## A page that does this

`docs/library/executors.md` is the worked example: a concept-first
intro that says what an executor *is*, a "Which executor should I
use?" decision table before any code, the closed and open models
explained as concepts — with the honest trade-off that an open model
piles up VUs and counts `dropped_iterations` when the target slows —
and only then the per-executor kwargs, with every table left exact.
Read it before reshaping another page.

## Before you commit

- Does the page open with what the feature *is*, or with how to call it?
- Can a reader who needs only the common case stop after the first
  paragraph?
- Is anything framed by its kwarg or CLI flag that should be named by
  concept instead?
- Are the programmatic and internals-facing parts clearly marked
  opt-in?
- Did you run every new or changed example by hand, and leave every
  table, metric name, exit code, and cross-reference exact?
- Did `just build-docs` stay clean — no new warning, no broken
  cross-reference?
