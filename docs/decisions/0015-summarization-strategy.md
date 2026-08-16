# 0015 — SummarizationStrategy

## Status

Accepted.

## Context

`contextshift/summarization/` (ADR 0007) has existed since early in this
project as a domain service — `Summarizer.summarize(messages) -> str` —
but nothing in `contextshift/strategies/` ever used it. Every shipped
`ContextStrategy` (`PinnedRecencyStrategy`, `RecencyStrategy`,
`SlidingWindowStrategy`) manages a budget the same way: pick a subset of
the original messages, discard the rest. That's a real limitation for
any conversation where the discarded messages still matter — a strategy
that compresses instead of discarding is a genuinely different point in
the design space, not a variation on the existing three.

## Decision

**`SummarizationStrategy`** (`contextshift/strategies/summarization_strategy.py`)
keeps the most recent `keep_recent` messages verbatim and replaces
everything older with a single summary message, produced by a
`Summarizer`. If the conversation is no longer than `keep_recent`, or
`summarize_older=False`, it falls back to the same oldest-first pruning
every other strategy in this package already does — there's nothing to
summarize, or the caller explicitly opted out of paying for a model
call.

**Constructor takes a `tokenizer`, beyond the literal
`SummarizationStrategy(summarizer, keep_recent, summarize_older)`
shape.** The summary is new text this strategy generates, not text that
arrived already measured the way every fixture or application message
is. Something has to measure it before it can be counted against
`budget`, the same way `ContextManager` itself requires a `Tokenizer`
for the same reason. Omitting it would either leave the summary
message's `token_count` as `None` (silently breaking `total_tokens()`
the first time this strategy's own pruning tries to use it) or hardcode
one specific tokenizer inside the strategy, which is exactly the kind
of implicit dependency this project has consistently avoided.

**Three consequences of depending on a real `Summarizer` are named
explicitly in the class docstring, not left for a caller to discover:**

- **Selection now costs a model call.** For the other three strategies,
  `build()` is pure computation and `latency_seconds` in a benchmark
  result is close to noise. Here it's a real number, reflecting network
  time.
- **It is not deterministic unless the `Summarizer` it's given is.**
  `contextshift.testing.FakeSummarizer` — a genuine subclass of
  `Summarizer`, not a new Protocol, so it satisfies any `isinstance`
  check or type hint a real one would — wraps `FakeLLMProvider` to
  return a fixed, configured string for any input. This is what makes
  `SummarizationStrategy` runnable inside `run_needle_benchmark()`'s
  deterministic, no-network tier at all (see
  `tests/test_needle_summarization_integration.py`), the same job
  `FakeLLMProvider` already does for anything depending on `LLMProvider`
  directly. Introducing `FakeSummarizer` as a subclass, rather than a
  new `Summarizer` Protocol, keeps ADR 0007's deliberate deferral of a
  pluggable summarization interface intact — this still isn't a second
  concrete implementation of "how to summarize," just a test double for
  the one that exists.
- **`ContextResult.excluded` means something subtly different here.**
  For the other three strategies, an excluded message is genuinely
  gone. For `SummarizationStrategy`, an "excluded" older message was
  compressed into the summary, not necessarily lost — the fact it
  contained may still be present, paraphrased, in the kept summary
  message's content. This matters concretely for
  `contextshift.benchmark.needle`: its identity-based matching
  (`id()`, ADR 0013) will report a summarized message as *not*
  retained even when the summary preserves exactly the fact a probe
  needed. That's a named, honest limitation of applying needle
  retention to this strategy — not a bug in either needle retention or
  `SummarizationStrategy` — and a caller who wants the real picture for
  this strategy specifically should use the opt-in judge tier
  (`run_judged_benchmark()`, ADR 0013), which asks the actual question
  against the actual selected context instead of checking object
  identity.

**Recent-window pruning still respects budget.** If `summary_message`
plus the full `keep_recent` window still exceeds `budget.effective_limit`
(a large summary, or a small budget), the recent window is pruned
oldest-first — the same never-drop-the-last-message discipline every
other strategy in this package already follows — rather than silently
producing a `ContextResult` that overflows the budget it was given.

## Consequences

**Easier:** a caller who wants "compress, don't just discard" gets a
strategy that fits the same `ContextStrategy` interface as the other
three, benchmarkable in the same harness, testable without network
access via `FakeSummarizer`. `contextshift.testing` now documents a
real, deliberate cross-subpackage dependency
(`contextshift.testing` → `contextshift.summarization`) rather than
staying purely a facade over `contextshift.llm`.

**Harder:** `SummarizationStrategy` is the only strategy whose
constructor requires two collaborators (`summarizer` and `tokenizer`)
instead of zero or one scalar. A caller who forgets to pass a
deterministic `Summarizer` in a test or CI context will get real
non-determinism, not a loud error — the same trade-off `LLMProvider`
already carries.

**Forecloses:** treating needle retention as the complete picture for
compression-based strategies going forward. Any future strategy that
compresses rather than discards inherits the same identity-matching
blind spot documented here, not a new one to rediscover.

## Addendum: SummarizationStrategy is excluded from the published needle-retention table

The Decision section above named the limitation; this addendum records
the concrete choice that followed from it, once it came time to decide
what actually appears in README.md's and `docs/benchmarks/needle.md`'s
headline table.

**The problem is sharper than "identity matching undercounts a
real summary."** `FakeSummarizer` — the only `Summarizer` the
deterministic tier can use — doesn't summarize anything. It returns a
fixed placeholder string (`"[FAKE SUMMARY]"` by default) regardless of
input. Running `SummarizationStrategy` through
`run_needle_benchmark()` with `FakeSummarizer` wouldn't just
undercount a real summary's fact-preservation the way the Decision
section describes — it would report a number for a summary that, by
construction, never contains any fact any probe could ask about. That
number would look like a measurement and be closer to a constant: no
`FakeSummarizer` configuration can make it score above whatever
verbatim `keep_recent` window happens to satisfy on its own. Publishing
it next to three real, differentiated needle-retention numbers would
misrepresent it as comparable evidence, when it measures nothing about
summarization quality at all.

**Decision: `SummarizationStrategy` does not appear in
`contextshift.benchmark.__main__`'s `needle`/`standard` suites, the
README's needle-retention table, or `docs/benchmarks/`.** Between the
two options this addendum considered —
(a) evaluate it through the opt-in judged tier instead, with the
omission explained where the table would otherwise expect it, or
(b) build a deterministic "extractive" fake summarizer (e.g., first
sentence of each dropped message) so it produces *some* comparable
needle-retention number —
**(a) was chosen.** (b) was rejected because an extractive fake would
still not be summarization — it would produce a number that looks like
real evidence about `SummarizationStrategy` while actually measuring a
compression heuristic nothing ships or recommends, the same
misrepresentation risk the Decision section already rejected for
`FakeSummarizer`, just moved one level down. A caller reading "45%
needle retention" next to `SummarizationStrategy` would reasonably
assume that reflects the strategy's actual behavior with a real
`Summarizer` — it wouldn't.

**What "evaluate it through the judged tier instead" concretely means:**
`SummarizationStrategy` is a completely ordinary `ContextStrategy` as
far as `run_judged_benchmark()` is concerned — no strategy-specific
code exists or is needed there. What's new is a test proving the
wiring works end to end
(`tests/test_needle_summarization_integration.py::test_summarization_strategy_runs_cleanly_through_the_judged_benchmark`),
using `FakeSummarizer` and `FakeLLMProvider` together so it stays
network-free — a smoke test for the plumbing, not a quality
measurement, since neither fake produces a real summary or a real
answer. **The tier that actually answers "does `SummarizationStrategy`
preserve enough for a real model to answer correctly" is
`run_judged_benchmark()` given a real `Summarizer` and a real
`LLMProvider`** — not exercised in this repository's own CI, for the
same reason `run_judged_benchmark()` is opt-in at all (ADR 0013): it
costs money and calls a network. A caller evaluating
`SummarizationStrategy` for their own use should run it that way
themselves, against their own fixtures if the ones here don't match
their domain.

README.md's needle-retention table carries a one-line note pointing
here for exactly this reason, rather than silence that would read as
an oversight.
