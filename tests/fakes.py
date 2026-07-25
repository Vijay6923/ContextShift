"""
Test doubles shared across test files. Deliberately not part of
contextshift/ itself -- see docs/decisions/0006-llm-provider-interface.md
for why a fake provider stays in the test suite rather than becoming a
contextshift.testing subpackage nothing currently needs.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence

from contextshift.core import Message


class FakeLLMProvider:
    """
    An in-memory LLMProvider (contextshift.llm.base.LLMProvider) -- no
    network calls, no API key, no HTTP.

    Exists for two reasons: it validates that LLMProvider is a genuinely
    satisfiable, well-designed interface (a trivial in-memory
    implementation conforming to it cleanly, with none of GroqProvider's
    transport complexity, is a good sign the interface drew the right
    line between "provider" and "everything else"); and it lets tests of
    anything that depends on an LLMProvider (future summarization tests,
    for instance) inject a fake instead of hitting a real network.

    Records every call it receives (`complete_calls`, `stream_calls`) so
    a test can assert on what a caller actually sent, not just what the
    fake returned.
    """

    def __init__(
        self,
        complete_response: str = "fake completion",
        stream_chunks: Sequence[str] = ("fake ", "stream ", "response"),
    ) -> None:
        self._complete_response = complete_response
        self._stream_chunks = list(stream_chunks)
        self.complete_calls: list[tuple[list[Message], int]] = []
        self.stream_calls: list[tuple[list[Message], int]] = []

    def complete(self, messages: Sequence[Message], max_tokens: int = 1024) -> str:
        self.complete_calls.append((list(messages), max_tokens))
        return self._complete_response

    def stream(self, messages: Sequence[Message], max_tokens: int = 1024) -> Iterator[str]:
        self.stream_calls.append((list(messages), max_tokens))
        yield from self._stream_chunks
