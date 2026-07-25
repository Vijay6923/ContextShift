# 0003 — Tokenizer scope excludes budget aggregation

## Status

Accepted.

## Context

`utils/token_manager.py` bundles four functions under one module:

1. `estimate_tokens(text) -> int` — measures one piece of text.
2. `get_total_tokens(messages) -> int` — sums the already-computed
   `token_count` of every message in a list.
3. `is_over_limit(messages) -> bool` — compares that sum against
   `Config.MAX_TOKENS - Config.TOKEN_SAFETY_MARGIN`.
4. `get_token_stats(messages) -> dict` — builds the `{current_tokens,
   max_tokens, percentage}` shape the `/messages` route returns to the
   frontend for the token-usage progress bar.

The original migration plan (Step 3, as scoped before this step began)
described porting "token_manager.py" wholesale into `tokenizers/`. Doing
the work surfaced that this doesn't hold up under the definition of a
tokenizer given for this step: *"the tokenizer should only answer one
question: how many tokens does this message approximately consume."*
Only function 1 answers that question. Functions 2-4 don't measure text
at all -- they read a field (`token_count`) that's already been computed
and reason about it relative to a budget or for display. Bundling them
into `tokenizers/` would mean the tokenizer subpackage knows about
`Message` lists, `TokenBudget`-shaped comparisons, and JSON-shaped
reporting output -- exactly the "context building" and "strategy"
knowledge this step's instructions say a tokenizer must not have.

## Decision

`contextshift/tokenizers/` contains only `estimate_tokens` (as a free
function) and `HeuristicTokenizer` (a class satisfying the `Tokenizer`
protocol), both operating on a single `text: str` argument.

Functions 2-4 are **not ported in this step**. Their eventual homes are
deferred to Step 4, where each is expected to land differently:

- `get_total_tokens` most likely becomes a small helper inside
  `strategies/` (or a `TokenBudget` method) that sums `Message.token_count`
  across a list -- it's a strategy-level aggregation, not a tokenizer
  concern.
- `is_over_limit` is a direct comparison against
  `TokenBudget.effective_limit` (introduced in Step 2) and likely
  disappears as a standalone function, folded into wherever the pruning
  loop is ported.
- `get_token_stats` is presentation-shaped output for one specific Flask
  route (`/messages`'s progress-bar JSON) and is a strong candidate for
  staying application-side entirely, computed by the adapter layer from
  a `TokenBudget` and a summed token count, rather than becoming part of
  the library's public surface at all.
- `log_token_info`'s print-based tracing is very likely superseded by
  the `ContextResult.trace` concept already planned for Step 4's
  `ContextStrategy` interface, rather than ported as-is.

This decision only commits to what tokenizers/ does *not* own; where
functions 2-4 land is intentionally still open, to be settled together
with the algorithm that actually uses them.

## Consequences

**Easier:** `contextshift/tokenizers/` has a genuinely single
responsibility and zero dependency on `contextshift.core` or anything
else in the package -- it operates on plain strings. A future
tiktoken-backed or provider-native tokenizer is a drop-in `Tokenizer`
implementation with no exposure to messages, budgets, or strategies at
all.

**Harder:** none identified -- this is a narrower Step 3 than originally
scoped, not a more complex one.

**Forecloses:** treating "was in the same legacy file" as sufficient
reason for two pieces of logic to end up in the same library subpackage.
The legacy module's grouping reflected convenience in a single-file
Flask app, not a domain boundary.
