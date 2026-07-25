"""
Context-management strategies.

The heart of the framework: a common ContextStrategy interface plus
concrete strategies (starting with the pinned/recency-window policy
carried over from the original application) that select which messages
belong in an LLM's context under a token budget. New strategies are
added by implementing ContextStrategy, without modifying any existing
strategy or the application that consumes them.

A registry for looking up strategies by name is intentionally not part
of this step -- with exactly one strategy in existence, a registry has
nothing yet to register. It's a natural, low-risk addition once a second
strategy exists to make the choice between them meaningful.
"""
from contextshift.strategies.base import ContextResult, ContextStrategy
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy

__all__ = ["ContextStrategy", "ContextResult", "PinnedRecencyStrategy"]
