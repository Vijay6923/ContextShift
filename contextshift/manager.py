"""Stateless orchestration of a strategy and a provider into a chat turn."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from contextshift.core import Message, TokenBudget
from contextshift.llm.base import LLMProvider
from contextshift.strategies.base import ContextResult, ContextStrategy
from contextshift.tokenizers.base import Tokenizer


@dataclass(frozen=True, slots=True)
class ChatResult:
    """
    The outcome of a single ContextManager.chat() call.

    Deliberately transparent, not reduced to a bare string: `context` is
    the strategy's own ContextResult, unmodified, so a caller can inspect
    exactly what was kept and excluded -- the same data
    `ContextStrategy.build()` already exposes, not a new concept.
    `user_message` is the just-constructed Message for the caller's own
    input text, with its token_count already measured, so persisting it
    doesn't require re-measuring anything.

    Args:
        response: The provider's complete reply text.
        context: The ContextStrategy's ContextResult for this call --
            what was selected and what was excluded. This is the
            strategy's own output, not re-shaped by ContextManager.
        user_message: The caller's `user_message` string, wrapped as a
            Message with a measured token_count. Not yet persisted --
            persistence is a caller concern (see
            docs/decisions/0011-framework-v2-design-review.md's
            Non-goals section).

            Note (Framework Phase 2): app.py's real `chat()` caller
            (`/upload`'s PDF path) does not end up using this field --
            it must persist the user's message *before* calling the
            provider, to preserve the app's existing behavior of
            keeping that message even if the provider call then fails,
            and `chat()` only returns after the provider call succeeds.
            Kept provisionally rather than removed: a caller without
            that ordering constraint (e.g. a future non-persisting
            consumer) would still use it as designed. Revisit once a
            second real consumer exists.
    """

    response: str
    context: ContextResult
    user_message: Message


class ContextManager:
    """
    Orchestrates a ContextStrategy and an LLMProvider into a chat turn:
    history -> strategy -> provider -> response. Nothing more.

    Extracted from a real duplication, not designed speculatively: the
    original application's Flask routes (`/chat`, `/upload`'s PDF path)
    each independently wrapped a new user message, queried history,
    selected context via a strategy, and called a provider -- the same
    four-step sequence, written out twice with no shared abstraction
    between them. See docs/decisions/0011-framework-v2-design-review.md
    for the full "who is the concrete consumer" reasoning behind every
    method below, and for what this class deliberately does not do.

    Stateless: does not hold conversation history, does not persist
    anything, does not decide when to summarize, does not catch or
    reformat exceptions from the strategy or provider. `history` is an
    explicit argument on every call, exactly like
    `ContextStrategy.build()` already requires -- ContextManager adds
    no state of its own beyond its four constructor dependencies, which
    themselves never change after construction.

    Provider-specific call options (e.g. how many tokens a reply may
    use) are not exposed here -- they stay on the provider, which a
    caller configures directly (e.g. at construction, or by wrapping it)
    rather than routing through ContextManager. Neither real consumer
    this class was extracted from ever varies such an option per call.

    Args:
        strategy: Selects which of `history` (plus the new user message)
            fit the budget.
        provider: Actually talks to a model.
        tokenizer: Measures the token cost of the caller's raw
            `user_message` string, so it can be wrapped as a Message
            before being handed to `strategy`. Required, not optional --
            every real caller of the code this class was extracted from
            always supplied one; there is no code path today that needs
            ContextManager to work without measuring the new message.
        budget: The token ceiling `strategy` selects against. Fixed for
            this manager's lifetime, matching how the one real caller
            never varies it per call.
        system_prompt: Prepended as a system-role message ahead of
            whatever `strategy` selects, for the provider call only --
            it is never included in the `ContextResult` a caller
            inspects, since a system prompt is a caller's framing
            choice, not part of what the strategy decided (ADR 0004).
            Optional and unopinionated: `None` (the default) means
            nothing is prepended. ContextManager only orchestrates
            *where* a system prompt goes; it never decides *what* one
            says, extending the same boundary already drawn for
            ContextStrategy (ADR 0004) and LLMProvider (ADR 0006).
    """

    def __init__(
        self,
        strategy: ContextStrategy,
        provider: LLMProvider,
        tokenizer: Tokenizer,
        budget: TokenBudget,
        system_prompt: str | None = None,
    ) -> None:
        self._strategy = strategy
        self._provider = provider
        self._tokenizer = tokenizer
        self._budget = budget
        self._system_prompt = system_prompt

    def chat(self, history: Sequence[Message], user_message: str) -> ChatResult:
        """
        Select context for `user_message` given `history`, call the
        provider once, and return the complete reply.

        Concrete consumer: `/upload`'s PDF-upload path (`app.py`), which
        calls this method via `adapters.build_context_manager().chat(...)`
        -- previously a hand-written sequence of `adapters.build_chat_context`
        followed by `adapters.build_provider().complete(context)`.

        Args:
            history: The conversation so far, in order. Not mutated.
            user_message: The new turn's raw text.

        Returns:
            A ChatResult with the reply text, the strategy's
            ContextResult, and the wrapped user Message.
        """
        wrapped_user_message, context_result = self._select_context(history, user_message)
        response = self._provider.complete(self._for_provider(context_result))
        return ChatResult(response=response, context=context_result, user_message=wrapped_user_message)

    def stream_chat(self, history: Sequence[Message], user_message: str) -> Iterator[str]:
        """
        Select context for `user_message` given `history`, and stream
        the provider's reply incrementally.

        Concrete consumer: the `/chat` route (`app.py`), which calls this
        method via `adapters.build_context_manager().stream_chat(...)`
        and accumulates the yielded chunks itself as they arrive.

        Context selection happens eagerly, before this method returns --
        only consuming the returned iterator is lazy, matching
        LLMProvider.stream() itself. A caller who also needs the
        strategy's ContextResult or the wrapped user Message for this
        turn should call `chat()` instead.

        Args:
            history: The conversation so far, in order. Not mutated.
            user_message: The new turn's raw text.

        Returns:
            The provider's reply, streamed incrementally.
        """
        _, context_result = self._select_context(history, user_message)
        return self._provider.stream(self._for_provider(context_result))

    def _select_context(self, history: Sequence[Message], user_message: str) -> tuple[Message, ContextResult]:
        wrapped = Message(
            role="user",
            content=user_message,
            token_count=self._tokenizer.estimate_tokens(user_message),
        )
        context_result = self._strategy.build(list(history) + [wrapped], self._budget)
        return wrapped, context_result

    def _for_provider(self, context_result: ContextResult) -> list[Message]:
        if self._system_prompt is None:
            return context_result.messages
        return [Message(role="system", content=self._system_prompt)] + context_result.messages
