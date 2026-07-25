"""Pinned/recency context-selection strategy."""
from __future__ import annotations

from collections.abc import Sequence

from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextResult, total_tokens

DEFAULT_RECENT_BUFFER = 6


class PinnedRecencyStrategy:
    """
    A ContextStrategy that always keeps pinned messages, always keeps the
    most recent `recent_buffer` non-pinned messages, and prunes older
    ("candidate") messages -- oldest first -- when the token budget is
    exceeded, falling back to trimming the recency window (down to a
    floor of one message) only once every candidate has been dropped.

    Returns a ContextResult of plain Message objects -- not an
    OpenAI-formatted list, and with no system prompt prepended; message
    selection and prompt formatting are different concerns (see
    docs/decisions/0004-context-strategy-interface.md).

    Algorithm:
        1. Split input messages into pinned and non-pinned.
        2. The last `recent_buffer` non-pinned messages are "recent";
           any earlier non-pinned messages are "candidates".
        3. While there are still candidates and the current selection
           (pinned + candidates + recent) exceeds the budget, drop the
           oldest remaining candidate.
        4. If still over budget once candidates are exhausted, drop the
           oldest remaining recent message, down to a floor of one --
           the single most recent message is never dropped, regardless
           of budget.
        5. Pinned messages are never dropped, at any stage -- but their
           tokens do count toward the budget the whole time, so a large
           enough pinned selection can still force candidates and recent
           messages down to nothing.

    Args:
        recent_buffer: How many of the most recent non-pinned messages
            are protected from candidate-style pruning. Must be at least
            1 -- see docs/decisions/0004-context-strategy-interface.md
            for why 0 is rejected rather than silently accepted (it is
            not simply "no recency window"; Python's slice semantics
            make `non_pinned[-0:]` equivalent to `non_pinned[0:]`, i.e.
            the entire list, which is very unlikely to be what a caller
            passing 0 actually intended).
    """

    def __init__(self, recent_buffer: int = DEFAULT_RECENT_BUFFER) -> None:
        if recent_buffer < 1:
            raise ValueError(f"recent_buffer must be at least 1, got {recent_buffer}")
        self._recent_buffer = recent_buffer

    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult:
        pinned = [m for m in messages if m.is_pinned]
        non_pinned = [m for m in messages if not m.is_pinned]

        recent = non_pinned[-self._recent_buffer :] if non_pinned else []
        candidates = non_pinned[: -self._recent_buffer] if len(non_pinned) > self._recent_buffer else []

        excluded: list[Message] = []

        def current_selection() -> list[Message]:
            return pinned + candidates + recent

        while candidates and total_tokens(current_selection()) > budget.effective_limit:
            excluded.append(candidates.pop(0))

        while len(recent) > 1 and total_tokens(current_selection()) > budget.effective_limit:
            excluded.append(recent.pop(0))

        return ContextResult(messages=current_selection(), excluded=excluded)
