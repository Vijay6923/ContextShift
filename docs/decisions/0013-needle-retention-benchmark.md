# 0013 — Needle-retention benchmark

## Status

Accepted.

## Context

ADR 0012 built `contextshift.benchmark`: deterministic comparison of
`ContextStrategy` implementations on messages kept/discarded, tokens
kept/discarded, percentage retained, and selection latency. That
benchmark has a real limitation, not a cosmetic one: every one of
those metrics is implied by a strategy's own definition.
`SlidingWindowStrategy(window_size=10)` keeping exactly 10 messages is
not a finding — it's the strategy's constructor argument, restated.
Comparing strategies on these metrics alone tells a reader how each
one is *configured*, not whether any of them is actually *good* at the
job the whole project exists to justify: deciding what to keep.

The question worth asking is different: when a strategy drops
messages, does it drop the ones a later question in the conversation
actually depends on? That's answerable without a model call — the
same determinism guarantee ADR 0012 already established — as long as
which messages are "load-bearing" for a given question is decided
once, by a human, before any strategy runs against the conversation.

## Decision

**`Probe`** (`contextshift/benchmark/probes.py`) records one checkable
question and the message indices required to answer it:
`question`, `load_bearing_indices`, and an optional `expected_answer`
used only by the opt-in tier (below). **`ConversationFixture`** pairs a
conversation with its probes, plus a `name` and `failure_mode` label.
Fixtures live as plain JSON in `tests/fixtures/conversations/` —
readable and forkable by a contributor with no Python required to
understand one, loaded by `load_fixture`/`load_fixtures`.

**`run_needle_benchmark()`** (`contextshift/benchmark/needle.py`) runs
every strategy against every fixture in a suite and reports two new
`BenchmarkResult` fields: `needle_retention` (the fraction of
load-bearing messages retained, across every probe in every fixture)
and `probes_satisfied` (how many probes had *every* load-bearing
message survive, as an `"X / Y"` string — partial credit doesn't
count, the same way a person missing one fact usually can't give a
complete answer). Matching a fixture's messages against a strategy's
kept messages is done by object identity (`id()`), not value equality
— the same discipline ADR 0004 already applies to
`ContextStrategy.excluded`, and for the same reason: two fixture
messages with coincidentally identical text must not collide.

**A separate, genuinely non-tautological function, not an extension of
`run_benchmark()`.** `run_benchmark()`'s signature (`messages, budget,
strategies`) has no probes to check against — there is nothing for a
"did it keep what mattered" question to be asked of. `run_needle_benchmark()`
takes fixtures instead of a bare message list; `BenchmarkResult` gained
two new *optional* fields (`None` by default) rather than a new result
type, so `to_csv()`/`to_markdown()` keep working for both call shapes,
adding the two extra columns only when a result actually carries that
data (`to_csv`/`to_markdown`'s existing shape for `run_benchmark()`
callers is completely unchanged).

**Fixture honesty.** Hand-annotating which messages are load-bearing
is a judgment call, and a maintainer annotating their own fixtures
against their own strategies can unconsciously favor whichever one
they're building. The fixture suite in this repository was written and
committed *before* any strategy was run against it — `_generate.py`
constructs each conversation and its probe indices mechanically, from
the conversation's own structure (e.g. "the correction message is the
one right after N filler exchanges"), not by inspecting any strategy's
output — and `run_needle_benchmark()` was only pointed at the fixtures
afterward, to see what came out. The actual results
(`docs/benchmarks/` once Phase 2 lands) are exactly what fell out of
that order of operations, not curated afterward. Any new fixture added
later should follow the same order: write the conversation and probes
first, run strategies against it second.

**The opt-in LLM-scored tier is a separate module, not a parameter on
`run_needle_benchmark()`.** `contextshift/benchmark/judge.py` defines
`Judge` (a `score(expected_answer, actual_answer) -> bool` Protocol)
and `run_judged_benchmark()`, which actually asks a real
`LLMProvider` each probe's question against a strategy's selected
context and scores the answer. This is the question needle retention
is a *proxy* for — surviving selection is necessary but not sufficient
for a model to actually answer correctly. Kept structurally separate,
in its own module, so importing `contextshift.benchmark`'s
deterministic tier never pulls in anything network-capable, and so it
stays unmistakably opt-in: nothing calls a model unless a caller
explicitly supplies both a provider and a judge. Results report mean
and standard deviation over repeated runs (default 3), never a single
number, since a real model's answers are not deterministic the way
everything else in this package is.

**Only one concrete `Judge` ships: `SubstringJudge`, plain string
matching, no model call.** An LLM-as-judge implementation was
considered and rejected as something this library ships — it would
require owning a judging prompt, which is exactly the kind of prompt
ownership every other interface in this project has deliberately
avoided (ADR 0004, ADR 0006, ADR 0007, ADR 0011's `system_prompt`
handling). A caller who wants LLM-as-judge scoring can write a `Judge`
that wraps an `LLMProvider` themselves; the interface doesn't require
this library to make that choice for them.

## Consequences

**Easier:** the benchmark table now says something a reader can't get
by reading a strategy's constructor arguments — e.g. two strategies
retaining a similar percentage of *tokens* while retaining very
different percentages of the *messages that actually mattered*, which
is exactly the distinction the old metrics couldn't surface. Fixtures
are forkable JSON, so a contributor can add a new failure mode without
touching any Python.

**Harder:** authoring a good fixture takes real care — a probe with
poorly chosen load-bearing indices (too few, or messages that aren't
truly necessary) understates or overstates what a strategy actually
preserved. This is a cost accepted deliberately, not a gap: a rushed
fixture is worse than no fixture, because it produces a confident,
wrong number.

**Forecloses:** treating token/message counts as sufficient evidence
that a strategy is "better." A strategy that reports high percentage
retention but low needle retention is retaining the wrong things
efficiently, which the old benchmark alone could not have shown.
