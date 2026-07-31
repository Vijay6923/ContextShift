"""Pure recency context-selection strategy."""
from __future__ import annotations

from collections.abc import Sequence

from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextResult, total_tokens


class RecencyStrategy:
    """
    A ContextStrategy that keeps as much of the conversation's tail as
    fits the budget -- no fixed window size, no candidate/recency
    split, no pinning. The baseline recency policy: budget-driven and
    nothing else.

    Algorithm:
        1. Start with every message.
        2. While more than one message remains and the total exceeds
           the budget, drop the oldest remaining message.

    That's the entire policy -- there is no constructor argument to
    configure, because there is nothing left to configure once pinning
    and a fixed window are both out of scope.

    How this differs from the other two strategies in this package:

    - **Vs. SlidingWindowStrategy**: SlidingWindowStrategy's primary
      selection is a fixed message *count* (`window_size`), with the
      budget checked only as a secondary constraint on that window.
      RecencyStrategy has no count parameter at all -- the budget is
      the only input that determines how many messages are kept, so
      the kept count varies naturally with each message's token cost.
    - **Vs. PinnedRecencyStrategy**: PinnedRecencyStrategy splits
      non-pinned messages into a protected `recent_buffer`-sized
      window and older "candidates," pruning candidates first and only
      reaching into the protected window if candidates alone can't fit
      the budget. RecencyStrategy has no such two-tier split or
      protected window -- every message, including the second-most-
      recent one, is prunable the moment the budget requires it.
      `Message.is_pinned` is never read.

    A note on the resulting behavior, not a coincidence worth hiding:
    for input with no pinned messages, `RecencyStrategy().build(...)`
    and `PinnedRecencyStrategy(recent_buffer=1).build(...)` select the
    identical trailing suffix of `messages` -- pruning oldest-first
    down to a floor of one is the same operation whether it's described
    as "no candidate/recent split" or as "a candidate/recent split with
    a one-message recent window." What `RecencyStrategy` adds over that
    specific configuration is a structural guarantee: there is no
    `is_pinned` check to accidentally trigger by pinning a message and
    getting different behavior, and no `recent_buffer` argument for a
    caller to get wrong. It exists for callers who want pure recency
    with no possibility of pinning semantics engaging, not because the
    selection algorithm itself is otherwise reachable no other way.

    Same floor-of-one guarantee as PinnedRecencyStrategy and
    SlidingWindowStrategy: the single most recent message is never
    dropped, regardless of budget.
    """

    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult:
        kept = list(messages)
        excluded: list[Message] = []

        while len(kept) > 1 and total_tokens(kept) > budget.effective_limit:
            excluded.append(kept.pop(0))

        return ContextResult(messages=kept, excluded=excluded)
