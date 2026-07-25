"""Behavioral contract every LLM provider satisfies."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Protocol, runtime_checkable

from contextshift.core import Message


@runtime_checkable
class LLMProvider(Protocol):
    """
    Anything that can turn a list of messages into a model-generated reply,
    either all at once or incrementally.

    A structural Protocol, not an ABC, per
    docs/decisions/0005-protocol-over-abc.md. Deliberately
    capability-oriented rather than vendor-oriented: nothing in this
    interface mentions Groq, OpenAI, or any specific wire format. A
    conforming implementation owns everything about *how* it talks to a
    model -- authentication, HTTP, retries, request payload shape,
    streaming protocol -- none of which is visible here. See
    contextshift.llm.groq.GroqProvider for the first implementation, and
    docs/decisions/0006-llm-provider-interface.md for what was
    deliberately left out of this interface and why.

    Takes `Message` (contextshift.core), not provider-specific dicts --
    every other part of this library speaks `Message`; a provider that
    instead expected callers to pre-format an OpenAI-shaped payload would
    leak a transport detail into every caller. Converting `Message` to
    whatever wire format a given provider actually needs is that
    provider's own responsibility.
    """

    def complete(self, messages: Sequence[Message], max_tokens: int = 1024) -> str:
        """Return a single, complete model reply to `messages`."""
        ...

    def stream(self, messages: Sequence[Message], max_tokens: int = 1024) -> Iterator[str]:
        """Yield a model reply to `messages` incrementally, chunk by chunk."""
        ...
