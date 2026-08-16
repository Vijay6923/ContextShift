---
name: New strategy proposal
about: Propose a new ContextStrategy (or Tokenizer/LLMProvider/VisionProvider implementation)
title: "New strategy: "
labels: enhancement, new-strategy
assignees: ""
---

## What policy does this implement?

Describe the selection policy in plain language — how does it decide
what survives a token budget? (e.g. "semantic similarity to the most
recent user message", "importance scoring via a secondary model
call".) Name how it's genuinely different from the four strategies
that already exist (`PinnedRecencyStrategy`, `RecencyStrategy`,
`SlidingWindowStrategy`, `SummarizationStrategy`) — see the
[Context Strategies table](../../README.md#context-strategies) and
[`docs/decisions/0012-strategy-framework-and-benchmark-review.md`](../../docs/decisions/0012-strategy-framework-and-benchmark-review.md).

## Interface conformance

Confirm this implements `ContextStrategy`
(`build(messages, budget) -> ContextResult`) as a structural `Protocol`
match — no inheritance from a ContextShift base class required (see
[ADR 0005](../../docs/decisions/0005-protocol-over-abc.md)).

## Determinism

Is `build()` pure computation, or does it depend on something
non-deterministic (a model call, an external service, randomness)? If
non-deterministic, what's the test-double/determinism seam — see
`contextshift.testing.FakeSummarizer` for the precedent
`SummarizationStrategy` established
([ADR 0015](../../docs/decisions/0015-summarization-strategy.md)) for
depending on a real model call while staying runnable in CI.

## Benchmarking

Have you run this strategy against the existing needle-retention
fixture suite (`tests/fixtures/conversations/`, via
`contextshift.benchmark.run_needle_benchmark`)? Paste the resulting
table if so — a strategy proposal is much easier to evaluate with a
real number attached than without one.

## New dependencies

Does this require a new third-party package? If so, is it a required
dependency or does it belong behind an optional extras group (see how
`tiktoken` and `anthropic` are scoped in `pyproject.toml`'s
`[project.optional-dependencies]`)?
