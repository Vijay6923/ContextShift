"""
Test doubles for building against contextshift without a real LLM
provider.

Public and importable independent of this repository's own test suite
-- unlike `tests/`, this module ships with the installed package. For a
CLI, notebook, benchmark, or evaluation harness exercising code built
on `ContextManager`/`LLMProvider` with no network calls, no API key,
and no HTTP.

This is the one deliberate exception to "an abstraction earns its
existence only when there's a concrete consumer inside this
repository": ADR 0006 originally kept `FakeLLMProvider` test-only
because nothing needed it publicly at the time. Framework v2 names
"eval harness" and "external developer" as target users this
repository's own test suite can't serve, which is what makes the
exception concrete rather than speculative -- see
docs/decisions/0011-framework-v2-design-review.md (Phase 3) for the
full reasoning.

Depends on `contextshift.summarization` (for `FakeSummarizer`, below)
in addition to `contextshift.core` -- a deliberate, new cross-subpackage
dependency, not an incidental one: `FakeSummarizer` exists specifically
to make `SummarizationStrategy` usable in a deterministic context (see
docs/decisions/0015-summarization-strategy.md), the same job
`FakeLLMProvider` already does for anything that depends on
`LLMProvider`.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence

from contextshift.core import Message
from contextshift.summarization import Summarizer


class FakeLLMProvider:
    """
    An in-memory LLMProvider (contextshift.llm.base.LLMProvider) -- no
    network calls, no API key, no HTTP.

    Records every call it receives (`complete_calls`, `stream_calls`) so
    a caller can assert on what was actually sent, not just what the
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


class FakeSummarizer(Summarizer):
    """
    A Summarizer (contextshift.summarization.Summarizer) backed by an
    in-memory, deterministic FakeLLMProvider -- no network calls.

    Exists for the same reason FakeLLMProvider does, one level up:
    `SummarizationStrategy` is the first `ContextStrategy` that
    depends on a real model call, which would otherwise make it
    impossible to run through `contextshift.benchmark`'s deterministic
    tier in CI. A genuine subclass of `Summarizer` -- not a separate
    Protocol -- so it satisfies any type hint or `isinstance` check a
    real `Summarizer` would, and so this stays exactly one line of
    setup instead of asking every caller to construct
    `Summarizer(FakeLLMProvider(...))` by hand.

    Args:
        summary_text: The fixed summary text returned for any input.
            Defaults to an unmistakably-fake placeholder so a test
            that forgets to check its actual content fails loudly
            instead of silently passing.
    """

    def __init__(self, summary_text: str = "[FAKE SUMMARY]") -> None:
        super().__init__(provider=FakeLLMProvider(complete_response=summary_text))
