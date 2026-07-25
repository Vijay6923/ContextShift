"""Behavioral contract every tokenizer implementation satisfies."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Tokenizer(Protocol):
    """
    Anything that can answer one question: how many tokens does a piece
    of text approximately consume?

    Deliberately a structural Protocol, not an abstract base class -- a
    tokenizer is defined entirely by this one behavior, not by any shared
    implementation or inheritance relationship. A future tiktoken-backed
    tokenizer, or a provider-native tokenizer that calls a vendor's
    counting endpoint, satisfies this interface simply by having a
    matching `estimate_tokens` method; it does not need to inherit from
    anything in this package, and strategy code that depends on
    `Tokenizer` does not need to change when a new implementation is
    introduced.

    A Tokenizer knows only how to measure text. It has no knowledge of
    Message, conversations, strategies, token budgets, or how its result
    will be used -- those are the concerns of whatever calls it.
    """

    def estimate_tokens(self, text: str) -> int:
        """Return the approximate token count for `text`."""
        ...
