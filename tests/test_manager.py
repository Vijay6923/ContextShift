"""
Unit tests for ContextManager covering behavior not already proven by
the legacy-orchestration comparison in test_manager_characterization.py:
constructor requirements, the system_prompt=None case, laziness of
streaming, that history is never mutated, and that exceptions propagate
unmodified (no hidden error handling -- a design requirement of Phase 1,
not an accident).
"""
import pytest

from contextshift import ContextManager
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.testing import FakeLLMProvider
from contextshift.tokenizers import HeuristicTokenizer

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)


def _manager(provider=None, **kwargs):
    return ContextManager(
        strategy=PinnedRecencyStrategy(),
        provider=provider or FakeLLMProvider(),
        tokenizer=HeuristicTokenizer(),
        budget=BUDGET,
        **kwargs,
    )


def test_system_prompt_defaults_to_none_and_nothing_is_prepended():
    fake = FakeLLMProvider()
    _manager(fake).chat([], "hello")

    sent_messages, _ = fake.complete_calls[0]
    assert sent_messages[0].role == "user"
    assert sent_messages[0].content == "hello"


def test_system_prompt_when_given_is_prepended_exactly_once():
    fake = FakeLLMProvider()
    _manager(fake, system_prompt="Be terse.").chat([], "hello")

    sent_messages, _ = fake.complete_calls[0]
    assert sent_messages[0] == Message(role="system", content="Be terse.")
    assert len([m for m in sent_messages if m.role == "system"]) == 1


def test_does_not_pass_max_tokens_the_providers_own_default_applies():
    # ContextManager has no max_tokens parameter -- provider-specific
    # call options stay on the provider. FakeLLMProvider.complete's own
    # default (1024) is what ends up recorded, because ContextManager
    # never passes the argument at all.
    fake = FakeLLMProvider()
    _manager(fake).chat([], "hello")
    _, received_max_tokens = fake.complete_calls[0]
    assert received_max_tokens == 1024


def test_history_is_not_mutated():
    history = [Message(role="user", content="hi", token_count=5)]
    original = list(history)

    _manager().chat(history, "another message")

    assert history == original


def test_new_user_message_token_count_is_measured_not_guessed():
    fake = FakeLLMProvider()
    result = _manager(fake).chat([], "hello world")

    tokenizer = HeuristicTokenizer()
    assert result.user_message.token_count == tokenizer.estimate_tokens("hello world")


def test_stream_chat_selects_context_eagerly_not_deferred_into_the_iterator():
    # stream_chat() returns a bare iterator now -- there's no separate
    # result object to inspect for "was context already selected." The
    # only way to observe eagerness is: does a failing strategy raise
    # from the stream_chat() call itself, or only once the returned
    # iterator is consumed? It must be the former.
    class FailingStrategy:
        def build(self, messages, budget):
            raise RuntimeError("context selection ran eagerly")

    class UnreachableProvider:
        def complete(self, messages):
            raise NotImplementedError

        def stream(self, messages):
            raise AssertionError("must not be called -- context selection should fail first")

    manager = ContextManager(
        strategy=FailingStrategy(),
        provider=UnreachableProvider(),
        tokenizer=HeuristicTokenizer(),
        budget=BUDGET,
    )

    with pytest.raises(RuntimeError, match="context selection ran eagerly"):
        manager.stream_chat([], "hello")


def test_provider_exception_propagates_unmodified():
    class FailingProvider:
        def complete(self, messages, max_tokens=1024):
            raise ValueError("simulated provider failure")

        def stream(self, messages, max_tokens=1024):
            raise NotImplementedError

    with pytest.raises(ValueError, match="simulated provider failure"):
        _manager(FailingProvider()).chat([], "hello")


def test_strategy_exception_propagates_unmodified():
    class FailingStrategy:
        def build(self, messages, budget):
            raise RuntimeError("simulated strategy failure")

    manager = ContextManager(
        strategy=FailingStrategy(),
        provider=FakeLLMProvider(),
        tokenizer=HeuristicTokenizer(),
        budget=BUDGET,
    )

    with pytest.raises(RuntimeError, match="simulated strategy failure"):
        manager.chat([], "hello")


def test_pinned_messages_survive_through_context_manager():
    # Confirms the strategy's actual selection logic (not re-implemented
    # or approximated by ContextManager) is what runs -- pinned survives
    # even when candidates/recent would otherwise crowd it out.
    history = [
        Message(role="system", content="pinned", token_count=3900, is_pinned=True),
    ] + [Message(role="user", content=f"filler {i}", token_count=10) for i in range(6)]

    fake = FakeLLMProvider()
    result = _manager(fake, system_prompt=None).chat(history, "new")

    contents = [m.content for m in result.context.messages]
    assert "pinned" in contents
