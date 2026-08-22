# Writing

How this project writes prose, for humans and agents alike. It governs
`README.md`, `CHANGES`, release notes, commit messages, CLI and log
messages, docstrings, source comments, and MyST documentation pages —
every surface a reader reaches.

For environment setup, the gates, and pull request workflow, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Voice

Three surfaces, one voice. A docstring says what a caller may rely on; a
`CHANGES` entry says what changed; prose says what happens. All three
are present tense, lead with the thing being described, and stop. Why
it was built that way belongs in the commit message, which is
timestamped and attached to the diff.

The most useful editing operation is deleting the introductory sentence.

Lead with verbs and name concrete things. Put identifiers in backticks.
Prefer short declarative sentences, one operational fact each. Do not
explain Python or asyncio to Python developers; do explain this
project's semantics.

Type annotations describe shape. Documentation describes meaning. A
sentence that restates a signature has said nothing.

Use MUST, SHOULD, and MAY only where the normative sense is meant. Say
what actually happens rather than that something is "supported".

| Instead of                       | Prefer                             |
| --------------------------------- | ----------------------------------- |
| "We added…"                      | "`Worker.check` now accepts…"      |
| "New and improved"               | "`Engine.start` now…"              |
| "powerful", "seamless"           | state the capability                |
| "easily", "simply", "just"       | omit                                 |
| "simple", "obvious", "intuitive" | omit                                 |
| "robust"                         | name the failure that is handled    |
| "comprehensive"                  | name what is covered                |
| "production-ready"               | state the guarantee                 |
| "optimized", "blazingly fast"    | give the magnitude                  |
| "various fixes"                  | name the components                 |
| "under the hood"                 | omit unless observable              |
| "please note that", "note that"  | state the fact                      |
| "leverage", "utilize"            | "use"                                |
| "delve into"                     | "read", or omit                     |
| "best practices"                 | name the practice                   |
| "in order to"                    | "to"                                 |

## Who you are writing for

The default reader writes async Python scenario scripts — an
`@rampa.scenario` function that takes a `Worker` — and runs them with
`rampa run`. They are fluent in load-testing vocabulary (VUs, closed and
open models, arrival rates, percentiles, thresholds, often from k6) and
comfortable with async Python, but they do not know rampa's internals:
the headless `Engine` and its run controller, the metric engine,
executor scheduling, output backends, or the optional Rust accelerator.
Serve them first.

A second, smaller reader drives rampa programmatically — the headless
`Engine` from pytest, the TUI, the MCP server, CI comparison — or works
on rampa itself. Serve them too, but mark their material opt-in ("for
programmatic use", "advanced") so the default reader knows they can
stop. Never make the common case pay a comprehension tax for the
advanced one.

Rules that follow:

- **Second person, present tense, active.** "You ramp the arrival
  rate", not "The arrival rate is ramped". Address the reader who is
  doing the thing.
- **Concept before API surface.** Open by saying what the thing *is*
  and what it does for the reader. The surface — decorator kwargs, CLI
  flags, the threshold grammar — is the last detail they need, not the
  first. A page that opens with a kwarg list has buried the idea under
  its mechanics.
- **Say when they can stop.** Lead with the default and the
  reassurance: `constant-vus` covers most tests, the advanced parts are
  optional. Let a skimmer leave after one paragraph.
- **Grant permission, do not demand attention.** "Reach for this
  when…", "for programmatic use" — tell readers they are in the right
  place without implying they must read on.
- **Progressive disclosure.** Order by how many readers need it: the
  one-decorator scenario, then the one kwarg a few will tune, then a
  module-level `Config` with several scenarios, then driving the
  headless `Engine` directly. Each step is for a smaller audience than
  the last.
- **Lean on the pipeline.** The reader thinks scenario → executor →
  `Worker` iterations → metrics → thresholds → exit code; reinforce
  that chain when explaining where a feature sits. It is the mental
  model the whole framework hangs on.
- **Name the trade-off.** If a choice costs something — an open-model
  executor piles up VUs and drops iterations when the target slows —
  say so, and say what it buys ("the rate holds, so you measure the
  target at a load you chose"). State it; do not sell it.
- **Frame by concept, not by mechanism.** Do not headline a feature by
  its kwarg or CLI flag; that names the implementation surface, which
  is the reader's last concern. Name the concept ("maintain a fixed
  request rate", not `pre_allocated_vus`). Kwarg tables, the threshold
  expression grammar, and the exit-code table belong in a reference
  table or the API docs, and only there.

**What stays precise.** Warm the framing, never the facts. Executor
tables, the threshold expression grammar, metric names
(`http_req_duration`, `dropped_iterations`), exit codes, and class or
function cross-references carry meaning in their exact form — leave
them alone. The friendly voice belongs in the sentences *around* a
precise block, introducing it, not inside it paraphrasing it into
vagueness.

`docs/library/executors.md` is the page that does this well: a
concept-first intro that says what an executor *is*, a "Which executor
should I use?" decision table before any code, the closed and open
models explained as concepts, and only then the per-executor kwargs,
with every table left exact. Read it before reshaping another page.

## README

A README is the shortest path from "what is this?" to competent use,
not the project's autobiography.

The first sentence is a contract. It says what abstraction the reader
has been handed, concretely enough to tell this package apart from the
neighbouring one.

Get to a runnable command or snippet before anything the reader can
skip. A logo, a mission statement, a comparison matrix and three
paragraphs of history in front of the install line all cost the same
thing.

State the minimum Python version and meaningful platform constraints in
prose, not only in badges. `requires-python` in `pyproject.toml` is the
authority; the README must agree with it.

Examples are executable, not illustrative fiction. Never
`your-command <some-options>`. See
[Documented examples that run](#documented-examples-that-run) for which
blocks are executed and how to write one that qualifies.

Document the semantic model, not the flag list. `--help` already
enumerates flags; what it cannot say is precedence, filesystem effects,
what goes to stdout versus stderr, and what a non-zero exit means.

State defaults explicitly — defaults are API. State negative guarantees
where they exist. They establish boundaries faster than any amount of
description.

Headings stay conventional and stable, because people deep-link them.
Badges are few and load-bearing.

## Documented examples that run

Two independent mechanisms execute examples in this repo. Know which
one covers the block you are editing before you touch it.

**Docstring doctests run across `src/rampa` and `tests`.** `pytest`'s
`--doctest-modules` addopt (`pyproject.toml`) collects every `>>> `
prompt in every module, class, and function docstring under those two
`testpaths`. `ELLIPSIS` and `NORMALIZE_WHITESPACE` are enabled
globally, so `...` elides variable output and whitespace differences do
not fail a comparison. `# doctest: +SKIP` is not permitted — it tests
nothing. Do not downgrade a doctest to a non-executed block to make it
pass; fix the example or fix the code. Every function and method is
expected to carry a working doctest; if you cannot make one pass, stop
and ask rather than commenting it out or skipping it.

**No `doctest_namespace` fixture exists.** Neither the root
`conftest.py`, `tests/conftest.py`, nor the `rampa.pytest_plugin`
pytest plugin injects a name into doctest globals. A doctest block gets
nothing for free: `import` whatever it needs, in that line or an
earlier `>>> ` line in the same docstring. Fixtures such as `tmp_path`
are not available inside a doctest.

**Nearly every module carries a bare `>>> import rampa.<module>` smoke
doctest** at the top of its module docstring, so a module that fails to
import fails collection immediately. Keep this line when editing a
module docstring, and add it to any new module.

**`README.md` and `docs/` are not doctest-collected.** `README.md` is
not in `testpaths`, and there is no `--doctest-glob`, so a `>>> `
prompt placed in Markdown does nothing in this repo — do not add one
expecting it to run.

**Markdown examples run through a separate, explicit harness instead.**
`tests/test_docs_examples.py` regex-extracts plain ```` ```python ````
fenced blocks (no prompts) from named files by position, then either
loads the result as a rampa script through the public loader — the
`_SCRIPT_EXAMPLE_CASES` table, which also asserts the resulting
scenario names — or `exec`s it directly against a fresh namespace — the
`_PAGE_EXAMPLE_CASES` table. `tests/test_docs_contracts.py` separately
asserts that specific substrings are present or absent in specific doc
files, to catch public-surface drift such as a renamed export or a
removed CLI subcommand. Coverage is by file and block *position*, not
by convention: a Python fence only runs if its file has an entry in one
of those tables, and a block is identified by where it falls among the
```` ```python ```` fences on that page.

**Consequence for editors.** Inserting, removing, or reordering a
```` ```python ```` fenced block in a covered file shifts every later
block's index and can point the test at the wrong snippet without
failing loudly. Read `tests/test_docs_examples.py` before editing a
Python fence in `README.md`, `docs/getting-started/index.md`,
`docs/library/tutorial.md`, `docs/library/thresholds.md`,
`docs/library/executors.md`, or `docs/library/protocols.md`. Everything
outside that curated set is still manual — run every new or changed
example against the current public API by hand before committing.

The fence tag for an executed Markdown block is `python`, plain, no
prompts. Shell commands use `console` with a `$ ` prefix, per
[Code blocks](#code-blocks).

**Room to grow.** A prompted `>>> ` block added under `src/rampa` or
`tests` is collected from that moment with no configuration change.
Extending collection to Markdown would need a `testpaths` or
`--doctest-glob` change; until then, the fenced-block harness above is
the only executed-Markdown mechanism this repo has.

## The changelog

`CHANGES` is the changelog. Not `CHANGELOG.md`. It is rendered as the
project's changelog page (`docs/history.md`), modeled on Django's
release-notes shape — deliverables get titles and prose, not bullets.

**Release entry boilerplate.** Every release header is
`## rampa X.Y.Z (YYYY-MM-DD)`. The file opens with an unreleased block
prefaced by a single HTML comment asking maintainers and contributors
to add notes below it; new release entries land below the most recent
*released* entry, never between the comment and the unreleased header.

**Unreleased entries carry no lead paragraph and no version summary.**
Speaking for a release — what the version "is", "ships", or "focuses
on" — is presumptuous before its scope is final. Only the person
cutting the release writes that paragraph.

**A cut release opens with a multi-sentence lead paragraph.** Plain
prose, no italic. Open with the version as sentence subject ("rampa
X.Y.Z ships …") so the lead is self-contained when excerpted. Two to
four sentences telling the reader what shipped and who cares —
user-visible takeaways, not internal mechanism. Cross-reference detail
docs with `{ref}` to keep the lead compact.

**Each deliverable is a section, not a bullet.** Inside
`### What's new`, every distinct deliverable gets a `#### Deliverable
title` heading naming it in user vocabulary, followed by one to three
prose paragraphs explaining what shipped. Do not wrap a paragraph in
`- ` — bullets are for enumerable lists, not paragraph containers.
Cross-link detail docs so the prose stays focused.

**The deliverable test.** Before writing an entry, ask: "What's the
deliverable, in user vocabulary?" If that cannot be answered in one
sentence, the entry is not ready. Mechanism — helper internals, byte
counters, schema-validation locations — belongs in pull request
descriptions and code comments, not the changelog.

**Fixed subheadings**, in this order when present: `### Breaking
changes`, `### Dependencies`, `### What's new`, `### Fixes`,
`### Documentation`, `### Development`. Dev tooling (helper scripts,
internal automation) lives under `### Development`. A breaking change
shows the migration path with concrete inline code — a `# Before` /
`# After` fenced block — not a pointer to one. Dependency floor bumps
use the form `` Minimum `pkg>=X.Y.Z` (was `>=X.Y.W`) ``.

**PR refs `(#NN)`** sit at the end of each deliverable's prose body,
not in the `####` heading.

**When bullets are appropriate.** Catch-all sections (`### Fixes`,
occasionally `### Documentation`) with three or more genuinely small
items use bullets — one line each, never paragraphs. If a bullet swells
past two lines, promote it to a `#### Title` heading with a prose body.

**Anti-patterns.** Fragile metrics that go stale silently — token
ceilings, third-party version pins, percent benchmarks, exact byte
counts. Describe the capability, not the math. Internal jargon: private
symbols (leading-underscore identifiers), algorithm names exposed for
the first time, backend scaffolding. Walls of text dressed up as
bullets. Breaking changes buried mid-entry instead of given their own
subheading at the top.

**Summarization style.** When asked "what changed in the latest
version?", lead with the entry's lead paragraph (paraphrased if
needed), followed by each `####` deliverable heading under
`### What's new` with a one-sentence summary. Cite `(#NN)` only if
asked for source links. Do not invent versions, dates, or numbers not
present in `CHANGES`, and do not quote line numbers or file offsets —
those shift as the file evolves.

## Release notes

`CHANGES` is the permanent ledger; a release page is editorial. Lead
with one paragraph naming the headline change, then three to five
highlights, then link the full changelog.

Numbers over adjectives. "Cold start 41 ms to 6 ms" is a sentence;
"much faster startup" is a smell.

A list of merged commit subjects is a merge log wearing a release-note
hat. Put the hand-written highlights above it.

Versions are PEP 440 identifiers. Semantic-versioning meaning is
applied to the documented public API — which includes command names,
options, exit statuses, configuration keys, environment variables, and
serialized formats, not only imported Python symbols.

## Docstrings

The prime directive: never restate the type. The annotation is the
source of truth; the docstring carries what the annotation cannot.

Document the dimensions the type system cannot encode:

- **Mutation.** What it changes in place.
- **Ownership.** What the caller must close, release, or keep alive.
- **Ordering.** Whether results come back in a guaranteed order.
- **Timing.** What has finished by the time the call returns, or the
  awaitable resolves.
- **Failure.** Which exceptions are raised and what triggers each.
- **Idempotence.** Whether calling twice does anything the second time.
- **Concurrency.** Whether calls are coalesced, queued, or independent,
  and whether the object is thread-safe, process-safe, or fork-safe.
- **Units and ranges.** What a number means and what values are
  accepted.
- **Boundary behaviour.** What zero, empty, and the maximum do.
- **Platform.** Behaviour that differs by operating system or
  dependency version — including whether the Rust accelerator is
  present.
- **Security boundary.** What is executed, and what is only read.

The ambiguity worth resolving by example: whether "retry three times"
means three attempts or four. State it.

The first sentence stands alone; tooling truncates there. PEP 257
applies: triple double quotes, an imperative one-line summary ending in
a period, a blank line before any extended description. Do not repeat
an introspectable signature.

Follow the NumPy docstring convention (`ruff`'s `pydocstyle` is
configured for it) for every function and method:

    """Short description of the function or class.

    Parameters
    ----------
    param1 : type
        Description of param1.

    Returns
    -------
    type
        Description of the return value.
    """

**`NamedTuple` and dataclass fields document every field** in an
`Attributes` section:

    class MetricDelta(t.NamedTuple):
        """Comparison of a single metric stat between two runs.

        Attributes
        ----------
        metric : str
            Metric name, e.g. ``"http_req_duration"``.
        stat : str
            Stat compared, e.g. ``"p(95)"``.
        baseline : float
            Value from the baseline run.
        current : float
            Value from the current run.
        pct_change : float
            Percent change from baseline to current.
        """

Autodoc renders every field whether or not it is described, so an
undocumented `NamedTuple` field ships to the API reference as "Alias
for field number 0" and a dataclass field ships bare. Document all of
them — a class with three fields and two documented still ships a stub
for the third.

One docstring dialect per repository, enforced by the linter rather
than relitigated in review.

## Logging

Log messages are a reader-facing surface, held to the same voice rules
as everything else in this file.

- Use `logging.getLogger(__name__)` in every module; add a
  `NullHandler` in library `__init__.py` files. Never configure
  handlers, levels, or formatters in library code — that is the
  application's job.
- Lazy-format: `logger.debug("msg %s", val)`, not an f-string. The
  interpolation is skipped entirely when the level is filtered, and a
  `%s`-style template groups identically in log aggregators instead of
  producing one unique line per call site. Guard an expensive `val`
  with `if logger.isEnabledFor(logging.DEBUG)`.
- Message style: lowercase, past tense for events ("request sent",
  "connection established"), no trailing punctuation, short — put
  detail in `extra`, not the message string.
- Use `logger.exception()` only inside an `except` block when not
  re-raising. Use `logger.error(..., exc_info=True)` for a traceback
  outside an `except` block. Do not call `logger.exception()` and then
  `raise` — that duplicates the traceback.
- Never log a secret env var's value, only its name.

| Level     | Use for                        | Examples                             |
| --------- | ------------------------------- | -------------------------------------- |
| `DEBUG`   | Internal mechanics               | Request scheduling, connection pool state |
| `INFO`    | User-visible operations          | Test started, results summary          |
| `WARNING` | Recoverable issues, deprecation  | Connection retry, deprecated option    |
| `ERROR`   | Failures that stop an operation  | Target unreachable, invalid config     |

## MyST roles and cross-references

Any class, method, function, exception, or attribute that has its own
rendered API page is cited with the matching role — `{class}`,
`{meth}`, `{func}`, `{exc}`, `{attr}` — never with plain backticks. A
doc page without an explicit ref label uses `{doc}`; an internal anchor
uses `{ref}`. Plain backticks are correct for code syntax, env vars,
parameter names, and file paths that have no autodoc destination.

Every documentation page opens with an explicit `(anchor)=` target in
lowercase hyphenated form (`cli-run`, `api-reference`); a `{ref}` must
match its target's anchor exactly.

Link the first prose mention of any symbol that has a useful
destination on that page — Python objects, rampa APIs, CLI command
pages, topic pages, or an external tool or project. Use the most
specific target available. After the first linked mention on a page,
later mentions can stay plain unless distance or context makes another
link useful. Do not rely on a later reference section to satisfy the
first-mention rule: if the first occurrence would be a heading,
grid-card teaser, or introductory sentence, link that occurrence or
retitle the heading so the first prose mention can carry the link.
Leave command examples, code blocks, and literal configuration values
as code; link the surrounding prose instead.

Point the advanced reader at the deep-dive rather than inlining it, and
put the link where their interest peaks — on the phrase that made them
curious ("drive the engine yourself", "compare runs in CI") — not as a
standalone footnote the eye skips.

`just build-docs` catches a broken cross-reference; nothing else does —
build the docs before committing a page that adds or moves an anchor.

## Source comments

A comment ships only if it passes all three gates. Fail any: delete or
rewrite. Borderline: delete — borderline means the information is
reconstructible, which is what makes deletion cheap.

**Loss.** Three years from now, would losing this cost a maintainer
real time rediscovering intent, an invariant, a constraint, or a
failure mode the code and tests do not already make obvious?

**Elite.** Would SQLite, Redis, the Go standard library, or CPython
write this comment, at this length? Those projects state the
constraint and stop. They do not argue with an imagined objector.

**Upkeep.** Will it stay true without maintenance? A comment that
hand-syncs a value the code owns — a count, an offset, a line
reference, a duplicated constant — is false the first time that value
moves.

### Ceiling

One or two lines. A comment reaching four is either carrying several
facts, in which case split it, or arguing, in which case cut it to the
fact.

Rationale, alternatives weighed, and the story of how the code got here
belong in the commit message: timestamped, attached to the exact diff,
and free to maintain.

A comment often holds both a constraint and the deliberation that found
it. Keep the constraint, cut the deliberation. "Runs at most once per
second" survives; "this is the right trade for now" does not.

### Keep

- Why over how: upstream quirks, protocol and compatibility
  constraints, performance tradeoffs still part of the contract.
- Invariants, preconditions, ordering, lifetime, and concurrency
  requirements that types and tests cannot express.
- Code that looks wrong but is not, so a later cleanup does not
  reintroduce the bug.
- A high-level sketch of an algorithm whose local operations do not
  reveal the whole.

### Delete

- Narration of the next lines; code translated into English.
- Restated names, types, defaults, or control flow.
- Values duplicated from the code and hand-synced.
- Justification, hedging, or apology for a choice.
- Speculation about future requirements.
- History version control already holds, including commented-out code.
- Ticket and issue numbers. They say nothing to a reader without
  tracker access, and they rot when the tracker moves. Unfinished work
  goes in the tracker, not the source.
- Transient observations — "currently", "for now", "the latest
  release" — that go stale with no nearby edit.

### The upkeep gate in practice

It reaches values that track our own code. It does not reach frozen
external facts.

Bad (Delete):

    # There are 321 tests to complete for servers.

Good (Keep):

    # CPython < 3.11 has no ExceptionGroup, so this branch stays.

### Documentation exception

Minimal usage examples, and parameter, return, and raises entries on
public API are exempt from the loss gate — they serve the caller, not
the maintainer. They are exempt from nothing else. Ceiling: a good man
page entry. A doctest that runs is also a test, so the exception
follows the same shape into `rust/`: a rustdoc `///` comment and a
`# Examples` doctest are exempt for the same reason — a rustdoc example
is compiled and run.

## Terminology and capitalization

Pick the domain noun and keep it. If the code calls something a
scenario, do not call it a test case in one paragraph and a job in the
next. If the executor is `constant-vus`, write "VU" everywhere rather
than alternating with "worker" and "virtual user" — reserve "worker"
for the `Worker` object a scenario function receives.

Stable vocabulary is what makes search, deep links, and an agent's
retrieval work at all.

Python and PyPI keep their own capitalisation. Distribution names are
written as they are published.

Do not write counts into prose — how many symbols exist, how many
tests there are. They go stale silently and no reader needs them.
Counts that pin a fixture or guard an invariant are different, and
belong in code.

## Markdown

Prose wraps at 80 columns. Table rows, badge lines, and long links are
exempt, because breaking them harms rendering. A pull request or issue
body does not wrap at all: GitHub renders a single newline as a space
in a file and as a line break in a comment, so a wrapped comment body
arrives as ragged stubs.

GitHub alert blocks — `> [!NOTE]`, `> [!WARNING]` — render as literal
text outside GitHub, so reserve them for at most one load-bearing
warning per document. Write the sentence so it carries the fact on its
own, and a renderer that drops the marker loses nothing.

Do not use a local absolute path or an email address in anything
published.

## Code blocks

Code blocks are paste-and-run units: pasting one block runs exactly one
intended action. Executed examples are exempt — the test suite runs
them, nobody pastes them.

- **One command per block.** Multiple steps may share a block only when
  explicitly chained with `&&`, `;`, or `\` continuations — the chain
  is then one logical command.
- **Explanations go in prose above the block**, never as `#` comments
  inside it.
- **Command menus are per-command blocks with prose lead-ins**, not
  tables.
- **Shell commands use the `console` tag with a `$ ` prefix.** This
  separates interactive commands from scripts and enables prompt-aware
  copy.
- **Split long commands with `\`** — one flag or flag+value pair per
  indented continuation line, positional arguments last.

Good — run ruff with autofix:

```console
$ uv run ruff check \
    --fix \
    --show-fixes \
    .
```

Bad:

```console
# Run ruff with autofix
$ uv run ruff check . --fix --show-fixes
```

## Commits

```
Scope(type[detail]): concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject to 50 characters or fewer, excluding any trailing
`(#NN)` pull request reference, and wrap body lines at 72. Separate the
`why:` and `what:` blocks with a blank line.

Routine maintenance commits drop the colon and take a capitalised
description, which is what distinguishes them at a glance in
`git log --oneline`:

```
py(deps[dev]) Bump dev packages
ai(rules[AGENTS]) Judge comments by three gates
.tool-versions(uv) uv 0.12.3 -> 0.12.5
```

Everything that changes behaviour keeps the colon.

Common types:

- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting
- **ci**: Workflow and pipeline changes
- **py(deps)**: Dependencies
- **py(deps[dev])**: Dev dependencies
- **ai(rules[AGENTS])**: AGENTS.md rule updates
- **ai(claude[rules])**: Claude Code rule updates
- **ai(claude[command])**: Claude Code command changes

Example, drawn from this repo's own history:

```
queues(fix[drain]): Catch queue.Empty, not every exception

why: A distributed worker treated every exception raised while
draining its sample queue as "nothing available yet", so a real
failure was indistinguishable from an idle queue.

what:
- Narrow the drain loop's except clause to queue.Empty
- Let unexpected exceptions propagate
```

For a multi-line message, use a heredoc so the formatting survives:

```console
$ git commit -m "$(cat <<'EOF'
Scope(feat[detail]): Concise description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

### Release commits

Never create tags. Never push tags. The owner handles tagging and tag
pushes, because a tag triggers the publish workflow.

A release commit subject is plain and short: `Tag v<version>`. The
detailed why and what go in the body. Do not use the
`Scope(type[detail]):` format for a release — it buries the lede.

## Slop prevention

Treat AI slop as review-hostile noise, not as proof that text or code
is wrong. The goal is to maximise information density.

- **AI signatures.** No "Generated by", no conversational filler, no
  unexplained emoji, no tool metadata.
- **Brittle references.** No hard-coded line numbers, fragile file
  counts, dated "as of" claims, bare SHAs, or local absolute paths —
  unless they are strict evidentiary artefacts such as a benchmark log.
- **Diff narration.** Do not restate what moved, was renamed, or was
  removed in anything the reader holds alongside the diff: code,
  docstrings, README, `CHANGES`, or a pull request description. The
  diff and the commit message already carry it.
- **Branch-internal narrative.** Do not mention intermediate states,
  abandoned approaches, or "no longer" behaviour unless users of a
  published release actually experienced the old state — **the
  published-release test**: did users of the most recently published
  release ever experience this old name, old behaviour, or bug? If no,
  it is branch-internal narrative; it belongs in the commit message,
  not the artefact.
- **Low-value scaffolding.** No ownerless TODOs, unused
  future-proofing, debug artefacts, or defensive wrappers around
  failure modes nothing can reach.
- **Prose inflation.** The diction table under [Voice](#voice) governs;
  replace an inflated word with a concrete description of behaviour,
  constraints, or trade-offs.
- **Coded labels.** Write rules and findings as plain imperatives. No
  private shorthand labeling systems — `[R1]`, `Option B`, ranking or
  pass labels, agent-only planning names — unless the label is already
  a real public API, protocol term, metric name, version, issue or PR
  reference, ADR number, or user-facing domain vocabulary. Use
  descriptive nouns instead: behaviour names, capability names, runtime
  modes, output backends, measured concepts.

Scan a branch for coded labels with a shape-based search, so the policy
does not seed the exact labels it means to prevent. Check the diff:

```console
$ git diff \
    --unified=0 \
    main...HEAD \
    -- AGENTS.md CHANGES docs notes src tests \
  | rg -n '^\+[^+].*(\b[A-Z][0-9]{1,3}\b|\b[A-Z]{1,3}-[0-9]{1,5}\b|\b(pass|phase|level|category|class|stage)\s+([A-Z][0-9]{0,3}|[0-9]{1,3})\b|T[O]DO|T[B]D|placeholde[r])'
```

and the commit messages, which the policy covers too:

```console
$ git log \
    --format='%H%n%s%n%b%n---END---' \
    main..HEAD \
  | rg -n '(\b[A-Z][0-9]{1,3}\b|\b[A-Z]{1,3}-[0-9]{1,5}\b|\b(pass|phase|level|category|class|stage)\s+([A-Z][0-9]{0,3}|[0-9]{1,3})\b|T[O]DO|T[B]D|placeholde[r])'
```

**Durable source links.** Link to a pinned revision, never to trunk. A
pinned permalink is not a brittle reference; an unlinked SHA dropped
into prose is. `blob/main/…` links rot silently — the file moves,
lines shift, and the anchor lands on unrelated code while still
resolving.

- Prefer a release tag (`blob/v1.4.0/…`) — most durable, and it tells
  the reader which released version the claim held for.
- Otherwise use a 7-char commit ref (`blob/9a29b1a/…`) reachable from
  trunk, when there is no tag or the claim is about unreleased code.
  Never a pull-request-head SHA — it can be rebased or garbage-collected.
- Reserve `blob/main/…` for living documents meant to always show the
  latest state, such as a contributing guide.
- Line anchors (`#L120-L145`) are only safe on a pinned ref.

**Privacy and local paths.** Do not commit home directories
(`~/...`, `/home/...`, `/Users/...`), temporary or editor-cache paths,
personal checkout roots, personal email addresses, internal hostnames,
or secrets in anything tracked. Use repo-relative paths and public URLs
pinned to a stable tag or ref instead.

Preserve the "why". Never delete a comment documenting an invariant, a
protocol constraint, a platform quirk, or an upstream workaround —
those are the facts [Source comments](#source-comments) keeps, and
every other comment is judged by it. Preserve exact counts, dates, and
SHAs that serve as evidence in benchmark results, release notes, stack
traces, or lockfiles — evidence is immune to the brittle-reference rule
above.

Cleaning up slop found on a long-running branch: if the branch's own
history is still private, fix each causal commit with a `fixup!` /
`amend!` commit and `git rebase --autosquash` rather than adding a
correction on top. Leave trunk or a colleague's commits alone unless
they explicitly ask otherwise, and never rewrite shared history.
