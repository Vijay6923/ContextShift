"""
Context-management strategies.

The heart of the framework: a common ContextStrategy interface plus
concrete strategies -- PinnedRecencyStrategy (a pinned/recency-window
policy), SlidingWindowStrategy (a pure count-based window, no
pinning), and RecencyStrategy (pure budget-driven recency, no window,
no pinning) -- that select which messages belong in an LLM's context
under a token budget. New strategies are added by implementing
ContextStrategy, without modifying any existing strategy or the
application that consumes them. total_tokens() is a shared helper --
summing Message.token_count against a TokenBudget is something
essentially every budget-respecting strategy needs, so it's exported
alongside the interface rather than left as an internal detail of one
strategy.

There is no registry for looking up strategies by name yet: even with
three strategies in existence, nothing in this codebase selects between
them by string or config -- see
docs/decisions/0012-strategy-framework-and-benchmark-review.md (Section
6) for why that stays deferred until something concretely needs it.
"""
from contextshift.strategies.base import ContextResult, ContextStrategy, total_tokens
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy
from contextshift.strategies.recency import RecencyStrategy
from contextshift.strategies.sliding_window import SlidingWindowStrategy

__all__ = [
    "ContextStrategy",
    "ContextResult",
    "PinnedRecencyStrategy",
    "RecencyStrategy",
    "SlidingWindowStrategy",
    "total_tokens",
]
