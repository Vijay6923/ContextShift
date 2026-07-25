"""
Context-management strategies.

The heart of the framework: a common ContextStrategy interface plus
concrete strategies (currently PinnedRecencyStrategy, a pinned/recency-window
policy) that select which messages belong in an LLM's context under a
token budget. New strategies are added by implementing ContextStrategy,
without modifying any existing strategy or the application that consumes
them. total_tokens() is a shared helper -- summing Message.token_count
against a TokenBudget is something essentially every budget-respecting
strategy needs, so it's exported alongside the interface rather than
left as an internal detail of one strategy.

There is no registry for looking up strategies by name yet: with one
strategy in existence, a registry has nothing to register. It's a
natural addition once a second strategy exists to make the choice
between them meaningful.
"""
from contextshift.strategies.base import ContextResult, ContextStrategy, total_tokens
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy

__all__ = ["ContextStrategy", "ContextResult", "PinnedRecencyStrategy", "total_tokens"]
