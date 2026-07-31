"""Sliding-window context-selection strategy."""
from __future__ import annotations

from collections.abc import Sequence

from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextResult, total_tokens

DEFAULT_WINDOW_SIZE = 6


class SlidingWindowStrategy:
    """
    A ContextStrategy that keeps the most recent `window_size` messages
    by count, with no pinning support and no candidate/recency split --
    the count-driven policy named and scoped in
    docs/decisions/0012-strategy-framework-and-benchmark-review.md
    (Section 2) as genuinely different from PinnedRecencyStrategy's
    budget-driven, recency-protected policy.

    Ignores `Message.is_pinned` entirely -- every message is treated
    uniformly by recency. A caller needing pinned messages to always
    survive should use PinnedRecencyStrategy instead; this class does
    not grow a pinning mode, per ADR 0012's explicit "no pinning"
    scoping for this strategy.

    Still respects `budget`: the window is a count-based *starting*
    selection, not an exemption from the token ceiling every strategy
    is expected to honor (docs/decisions/0004-context-strategy-interface.md
    -- `budget` is in the shared `build()` signature precisely because
    every strategy, regardless of internal policy, needs to know how
    much room it has). If the windowed messages alone still exceed the
    budget, the oldest of them are pruned next, down to a floor of one
    -- the single most recent message is never dropped, matching
    PinnedRecencyStrategy's same floor.

    Algorithm:
        1. Keep the last `window_size` messages, in order; anything
           older is immediately excluded.
        2. While the kept window still exceeds the budget and more
           than one message remains, drop the oldest remaining kept
           message.

    Args:
        window_size: How many of the most recent messages to keep
            before considering the budget. Must be at least 1 -- a
            window of 0 messages is never a sensible selection policy,
            the same reasoning PinnedRecencyStrategy's `recent_buffer`
            already applies (see
            docs/decisions/0004-context-strategy-interface.md).
    """

    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE) -> None:
        if window_size < 1:
            raise ValueError(f"window_size must be at least 1, got {window_size}")
        self._window_size = window_size

    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult:
        messages = list(messages)

        if len(messages) > self._window_size:
            excluded = messages[: -self._window_size]
            kept = messages[-self._window_size :]
        else:
            excluded = []
            kept = list(messages)

        while len(kept) > 1 and total_tokens(kept) > budget.effective_limit:
            excluded.append(kept.pop(0))

        return ContextResult(messages=kept, excluded=excluded)
