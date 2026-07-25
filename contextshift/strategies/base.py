"""Behavioral contract every context-management strategy satisfies, plus small shared helpers."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from contextshift.core import Message, TokenBudget


@dataclass(frozen=True, slots=True)
class ContextResult:
    """
    The outcome of a single ContextStrategy.build() call.

    Deliberately small: two lists of Message, both plain domain objects.
    No LLM-provider-specific formatting (no OpenAI-style role/content
    dicts) and no hardcoded system prompt -- preparing a prompt for a
    specific provider is a different concern from selecting which
    messages belong in it, and is not this type's responsibility. No
    structured per-message reasoning either, for now -- see
    docs/decisions/0004-context-strategy-interface.md for why both of
    these were considered and deliberately excluded rather than built
    speculatively.

    Args:
        messages: The final, ordered set of messages a strategy decided
            to keep. Formatting these for a specific LLM call is a
            downstream concern, not this type's.
        excluded: Messages the strategy considered but did not keep, in
            their original relative order. Present so a caller can answer
            "what got dropped" directly, without re-deriving it by
            comparing the input against `messages` by hand.
    """

    messages: list[Message]
    excluded: list[Message]


@runtime_checkable
class ContextStrategy(Protocol):
    """
    Anything that can select which messages fit inside a token budget.

    Deliberately a structural Protocol (see
    contextshift.tokenizers.base.Tokenizer for the same reasoning applied
    there): a strategy is defined entirely by this one behavior. New
    strategies (semantic retrieval, importance scoring, hybrid policies)
    are added by implementing this method, not by inheriting from
    anything in this package -- and neither existing strategies nor the
    application that consumes them need to change when a new one is
    introduced.

    Strategy-specific configuration (e.g. how large a recency window a
    particular pinned/recency policy uses) belongs on the strategy's own
    constructor, not in this shared signature: it varies by strategy
    instance, not by call. `messages` and `budget` are the only two
    things every strategy, regardless of approach, needs to do its job.
    """

    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult:
        """
        Select which of `messages` fit within `budget`.

        Args:
            messages: Candidate messages to choose from, in their
                original conversational order. Not mutated by this call.
            budget: The token ceiling to respect.

        Returns:
            A ContextResult describing what was kept and what was excluded.
        """
        ...


def total_tokens(messages: Sequence[Message]) -> int:
    """
    Sum the token_count of every message in `messages`.

    Raises ValueError if any message's token_count is None (unmeasured),
    rather than silently treating it as zero -- see the invariant
    documented on contextshift.core.Message.token_count. Available to any
    ContextStrategy implementation that needs to compare a candidate
    selection against a budget; not part of the ContextStrategy interface
    itself, since not every conceivable strategy necessarily needs it
    (e.g. one that selects purely by message count).
    """
    total = 0
    for message in messages:
        if message.token_count is None:
            raise ValueError(
                f"Cannot total tokens: a message with role={message.role!r} "
                f"has no measured token_count (it is None)."
            )
        total += message.token_count
    return total
