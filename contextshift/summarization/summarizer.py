"""LLM-based conversation summarization."""
from __future__ import annotations

from collections.abc import Sequence

from contextshift.core import Message
from contextshift.llm.base import LLMProvider

DEFAULT_MAX_TOKENS = 512

_SYSTEM_PROMPT = (
    "You are a conversation summarizer. Summarize the following "
    "conversation excerpt into a single concise paragraph. Preserve all "
    "key facts, topics, and decisions. Be dense but accurate."
)


class Summarizer:
    """
    Compresses a list of messages into a single dense paragraph via an
    LLMProvider.

    Depends only on LLMProvider (contextshift.llm.base) -- never
    GroqProvider or any other concrete provider. Constructed with
    whatever provider the caller supplies, including a fake one for
    tests (see tests/fakes.py::FakeLLMProvider).

    Two things this class deliberately does NOT do, extending the same
    "application framing stays outside the library" pattern applied to
    ContextStrategy (ADR 0004) and LLMProvider (ADR 0006):
        - It does not decide whether summarization is worth doing (e.g.
          whether there are "enough" messages to bother) -- that's a
          caller decision.
        - It does not prepend a label like "[SUMMARY]" to its output.
          That's a display/storage convention for whatever application
          consumes the summary, not part of what "summarization" means
          as an operation.

    Args:
        provider: The LLMProvider used to actually call a model.
        max_tokens: Token budget for the generated summary. Exposed as a
            constructor argument rather than hardcoded internally --
            unlike GroqProvider's temperature (ADR 0006), how long a
            summary is allowed to be is a natural, expected dial on the
            summarization operation itself, not an incidental vendor
            detail. Defaults to 512. Must be positive.
    """

    def __init__(self, provider: LLMProvider, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")
        self._provider = provider
        self._max_tokens = max_tokens

    def summarize(self, messages: Sequence[Message]) -> str:
        """Return a dense-paragraph summary of `messages`, as produced directly by the provider."""
        conversation_text = self._build_conversation_text(messages)
        prompt = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=conversation_text),
        ]
        return self._provider.complete(prompt, max_tokens=self._max_tokens)

    @staticmethod
    def _build_conversation_text(messages: Sequence[Message]) -> str:
        # Any role other than "user" -- including "system" -- is labeled
        # "assistant" in the transcript. This means a prior summary
        # message (role="system"), if it were ever included as input,
        # would be transcribed as if the assistant had said it. See ADR
        # 0007 for the reasoning behind keeping this rule as-is.
        conversation_text = ""
        for message in messages:
            role = "user" if message.role == "user" else "assistant"
            conversation_text += f"{role}: {message.content}\n"
        return conversation_text
