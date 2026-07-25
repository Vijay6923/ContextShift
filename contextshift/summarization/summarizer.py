"""LLM-based conversation summarization, ported mechanically from the original application."""
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

    Ported mechanically from the original application's
    utils/summarizer.py::summarize_messages: identical prompt
    construction, including the exact system prompt text and the
    role-labeling rule in `_build_conversation_text` below. Not
    redesigned or given new prompting logic during this port -- see
    docs/decisions/0007-summarizer-domain-service.md.

    Depends only on LLMProvider (contextshift.llm.base) -- never
    GroqProvider or any other concrete provider. Constructed with
    whatever provider the caller supplies, including a fake one for
    tests (see tests/fakes.py::FakeLLMProvider).

    Two things this class deliberately does NOT do, both extending a
    pattern already established for ContextStrategy (ADR 0004) and
    LLMProvider (ADR 0006) -- excluding an application-specific framing
    concern from the library, not just this port happening to omit it:
        - It does not decide whether summarization is worth doing (e.g.
          whether there are "enough" messages to bother). The legacy
          equivalent of that check lived in the Flask route, not inside
          summarize_messages() itself; it remains a caller decision here.
        - It does not prepend a "[SUMMARY]" label to its output. That is
          a display/storage convention specific to how the original
          application tags summary messages in its chat history, not
          part of what "summarization" means as an operation.

    Args:
        provider: The LLMProvider used to actually call a model.
        max_tokens: Token budget for the generated summary. Exposed as a
            constructor argument rather than hardcoded internally
            because, unlike GroqProvider's temperature (ADR 0006), how
            long a summary is allowed to be is a natural, expected dial
            on the summarization operation itself, not an incidental
            vendor detail. Defaults to 512, matching the original
            application's one and only call site. Must be positive.
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
        # "assistant" in the transcript. A direct port of legacy's exact
        # rule, preserved even though it means a prior "[SUMMARY]"
        # message (role="system"), if it were ever included as input,
        # would be transcribed as if the assistant said it. See ADR 0007
        # for why this is kept rather than "fixed."
        conversation_text = ""
        for message in messages:
            role = "user" if message.role == "user" else "assistant"
            conversation_text += f"{role}: {message.content}\n"
        return conversation_text
