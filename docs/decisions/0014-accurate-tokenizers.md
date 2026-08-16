# 0014 — Accurate tokenizers, and the heuristic's real error rate

## Status

Accepted.

## Context

`HeuristicTokenizer` has always been described, honestly, as an
approximation — `contextshift/tokenizers/heuristic.py`'s own docstring
calls it "a rough, non-model-specific approximation, not a real
tokenizer." What it never had was a measured number: budget decisions
computed from a word-count heuristic could be off by some unknown
amount, and a strategy that "fits the budget" by the heuristic's count
could, in principle, overflow a real model's actual context window.
That's a correctness question with no answer on record.

## Decision

**`TiktokenTokenizer`** (`contextshift/tokenizers/tiktoken_backed.py`)
wraps OpenAI's `tiktoken` library — a real byte-pair-encoding
tokenizer, not an approximation of one. **`AnthropicTokenizer`**
(`contextshift/tokenizers/anthropic_native.py`) wraps Anthropic's own
`client.messages.count_tokens` endpoint — the exact count a Claude
model would use, at the cost of a real network call on every
`estimate_tokens()` (there is no local Claude tokenizer to run
offline, the same trade-off `GeminiVisionProvider` already accepts for
vision). Both are optional dependencies
(`pip install contextshift[tiktoken]` /
`pip install contextshift[anthropic]`); the underlying package import
is deferred to construction time in both classes, so
`from contextshift.tokenizers import TiktokenTokenizer` never requires
either package to be installed — only actually constructing one does,
with an error that names the install command rather than a bare
`ModuleNotFoundError`. `HeuristicTokenizer` remains the zero-dependency
default; nothing about its behavior changed.

**`contextshift.benchmark.tokenizer_bench`** compares tokenizers
against a reference the same way `contextshift.benchmark.needle`
compares strategies against fixtures: `benchmark_tokenizers(corpus,
reference, tokenizers)` reports mean absolute error, mean percentage
error, and worst-case percentage error per tokenizer. Living in
`contextshift/benchmark/` rather than `contextshift/tokenizers/`
keeps every piece of "measure something and report a number" logic in
one place, the same organizing principle ADR 0013 already established
for the strategy benchmark — "same harness, different axis," not a
new harness.

**The heuristic's actual error rate, measured against `TiktokenTokenizer`
(`cl100k_base`) over a 10-sample corpus spanning short phrases, code,
URLs, emoji/non-ASCII text, and long repeated content**
(`tests/test_tokenizer_bench.py::test_heuristic_tokenizer_error_rate_against_tiktoken_is_measured_not_assumed`,
reproducible directly — also runnable as
`python -m contextshift.benchmark --suite tokenizer`):

| Tokenizer | Mean Abs. Error | Mean % Error | Max % Error | Samples |
| --- | --- | --- | --- | --- |
| HeuristicTokenizer | 9.60 | 27.77% | 93.33% | 10 |
| TiktokenTokenizer | 0.00 | 0.00% | 0.00% | 10 |

(`TiktokenTokenizer` scoring zero error against itself is the harness's
own sanity check, not a claim about `TiktokenTokenizer`'s own accuracy
against a *different* reference, such as Anthropic's tokenizer — it
has none here to compare against.) A **~28% mean error, with a
worst-case near 100%**, is a real number a caller can now make a
decision against — e.g. whether `HeuristicTokenizer`'s speed and
zero-dependency footprint are worth that error margin for their
specific budget tightness, instead of an unquantified "it's rough."

## Consequences

**Easier:** a caller who needs accuracy for a tight budget has two
drop-in replacements — `TiktokenTokenizer` for a fast, local, close
proxy; `AnthropicTokenizer` for an exact count when calling Claude
specifically — with no change to any strategy, `ContextManager`, or
anything else that depends on the `Tokenizer` protocol. The error rate
above is testable and will be caught by CI if `HeuristicTokenizer`'s
formula ever regresses further from reality without anyone noticing.

**Harder:** two new optional dependencies for anyone who wants exact
counts, and `AnthropicTokenizer` introduces a real network call inside
what has otherwise been a synchronous, offline-friendly interface —
documented explicitly in its own docstring so a caller doesn't
discover it by surprise inside a hot loop.

**Forecloses:** describing `HeuristicTokenizer`'s inaccuracy vaguely
going forward. The number above is committed, checked by a test, and
reproducible by anyone — the same standard this project already holds
its benchmark claims to.
