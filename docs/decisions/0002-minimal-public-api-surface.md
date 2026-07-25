# 0002 — Minimal public API surface pre-1.0

## Status

Accepted. Supersedes the initial version of `contextshift.core.Message`
and the top-level `contextshift` re-exports introduced in Step 2, both
committed and then revised in the same review round.

## Context

While reviewing the first version of `contextshift.core`, three questions
came up that all reduce to the same underlying tension: how much should a
"stable public API type" commit to before there's a concrete consumer
forcing the decision?

1. `Message` initially included a `timestamp: datetime | None = None`
   field, justified by "some future strategy will likely need temporal
   reasoning." No strategy in the current design (pinned/recency,
   summarization, semantic retrieval as scoped so far) actually reads it
   -- the existing algorithm relies entirely on input-list order.
2. `Message.token_count` defaulted to `0`, mirroring the ORM column's
   `default=0`. But `token_manager.estimate_tokens()` floors at 1 for any
   non-empty text and the application rejects empty messages upstream, so
   in practice a *measured* value is never actually 0 today -- meaning
   `0` was already functioning as an accidental, unsafe "not measured"
   sentinel that a future Tokenizer measuring genuinely content-less
   input (e.g. a tool-call message) could collide with.
3. `contextshift/__init__.py` re-exported `Message` and `TokenBudget` at
   the top level, so `from contextshift import Message` worked in
   addition to `from contextshift.core import Message`.

## Decision

1. **`Message` does not have a `timestamp` field.** Reintroducing it is a
   purely additive, non-breaking change (a new optional field) the moment
   a concrete, designed strategy actually needs temporal reasoning beyond
   list order. Until then, carrying it on every `Message` instance is
   speculative API surface with no consumer.
2. **`Message.token_count` is `int | None`, defaulting to `None`**, not
   `int` defaulting to `0`. `None` unambiguously means "not measured
   yet"; `0` is reserved for an actual Tokenizer measurement of zero.
   Code that sums or otherwise aggregates token counts must treat `None`
   as missing data, not silently coerce it to zero.
3. **`contextshift/__init__.py` re-exports nothing.** Types are imported
   from their owning subpackage (`from contextshift.core import Message,
   TokenBudget`). Only `__version__`, which is genuinely package-level
   metadata with no owning subpackage, lives at the top.

The unifying principle across all three: **a field or export earns its
place by having a concrete, currently-designed consumer** -- not by being
plausible for some future strategy. This mirrors the "no premature API
surface" principle already stated in `docs/architecture.md`; this record
exists because the first pass at `Message` didn't fully live up to it,
and the gap was easier to name once made concrete in code and reviewed.

## Consequences

**Easier:** the public API surface at both the top level and within
`contextshift.core` is fully accounted for by things that are actually
used somewhere in the current design. Restructuring `contextshift/`'s
internals before 1.0 (moving a type between subpackages, reshaping
`core`) does not also mean breaking a top-level import path nobody had a
reason to rely on yet.

**Harder:** consumers write the slightly longer `from contextshift.core
import Message` rather than `from contextshift import Message`. Accepted
as a small, deliberate cost.

**Forecloses:** treating "a future strategy might want this" as
sufficient justification for adding a field or export during this
migration. A future addition should point at the specific strategy or
consumer that needs it, the way this decision now expects of any change
that follows it.
