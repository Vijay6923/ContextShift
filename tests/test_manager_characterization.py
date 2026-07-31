"""
Direct comparison between ContextManager and the orchestration sequence
duplicated across app.py's /chat route (streaming, via provider.stream)
and /upload's PDF path (non-streaming, via provider.complete), each of
which independently wraps a new user message, selects context via
adapters.build_chat_context, and calls a provider -- proving
ContextManager reproduces that sequence exactly, not just asserting it.

See docs/decisions/0011-framework-v2-design-review.md for why these two
routes are the concrete consumers ContextManager's public methods trace
to.

The exact system prompt text is duplicated here verbatim rather than
imported from adapters.py, for the same reason established in
test_strategy_characterization.py and test_llm_characterization.py:
owning this string is precisely what ContextManager does NOT do (ADR
0004, ADR 0011).
"""
import adapters
from config import Config
from contextshift import ContextManager
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.tokenizers import HeuristicTokenizer
from fakes import FakeLLMProvider

_CHAT_SYSTEM_PROMPT = (
    "You are a helpful assistant. The conversation history below may "
    "include a summary of earlier messages."
)


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def _manager(provider):
    return ContextManager(
        strategy=PinnedRecencyStrategy(recent_buffer=Config.RECENT_BUFFER),
        provider=provider,
        tokenizer=HeuristicTokenizer(),
        budget=TokenBudget(max_tokens=Config.MAX_TOKENS, safety_margin=Config.TOKEN_SAFETY_MARGIN),
        system_prompt=_CHAT_SYSTEM_PROMPT,
    )


SCENARIOS = {
    "typical_exchange": [
        _msg("user", "What's the capital of France?"),
        _msg("assistant", "Paris."),
        _msg("user", "And Germany?"),
        _msg("assistant", "Berlin."),
    ],
    "empty_history": [],
    "with_pinned_instruction": [
        _msg("system", "Always answer in French.", is_pinned=True),
        _msg("user", "Hello"),
        _msg("assistant", "Bonjour."),
    ],
    "over_budget_forces_pruning": (
        [_msg("user", f"old candidate {i}", token_count=1000) for i in range(4)]
        + [_msg("user", f"recent {i}", token_count=10) for i in range(6)]
    ),
}


def _reference_context(history, user_text):
    """
    What app.py's routes construct today: wrap the new user message with
    a HeuristicTokenizer, append it to history, then call
    adapters.build_chat_context on the combined list -- exactly the
    sequence /chat and /upload's PDF path each do by hand.
    """
    tokenizer = HeuristicTokenizer()
    wrapped_user = Message(role="user", content=user_text, token_count=tokenizer.estimate_tokens(user_text))
    all_messages = list(history) + [wrapped_user]
    expected_provider_input = adapters.build_chat_context(all_messages)
    return wrapped_user, expected_provider_input


def test_chat_matches_upload_pdf_path_orchestration():
    """Non-streaming: ContextManager.chat() vs. /upload's build_chat_context + provider.complete()."""
    for name, history in SCENARIOS.items():
        user_text = "a new question"
        wrapped_user, expected_provider_input = _reference_context(history, user_text)

        fake_provider = FakeLLMProvider(complete_response="a reply")
        result = _manager(fake_provider).chat(history, user_text)

        assert result.user_message == wrapped_user, name
        sent_messages, sent_max_tokens = fake_provider.complete_calls[0]
        assert sent_messages == expected_provider_input, name
        assert sent_max_tokens == 1024, name
        assert result.response == "a reply", name


def test_stream_chat_matches_chat_route_orchestration():
    """Streaming: ContextManager.stream_chat() vs. /chat's build_chat_context + provider.stream()."""
    for name, history in SCENARIOS.items():
        user_text = "another question"
        _, expected_provider_input = _reference_context(history, user_text)

        fake_provider = FakeLLMProvider(stream_chunks=["Hello", " world"])
        chunks = list(_manager(fake_provider).stream_chat(history, user_text))  # lazy; exhaust it
        assert chunks == ["Hello", " world"], name

        sent_messages, sent_max_tokens = fake_provider.stream_calls[0]
        assert sent_messages == expected_provider_input, name
        assert sent_max_tokens == 1024, name


def test_chat_produces_exactly_the_expected_provider_call():
    """
    A single, minimal, from-first-principles proof that chat() calls the
    provider with exactly the message list expected -- system prompt
    prepended, history preserved in order, new user message appended --
    hand-computed here rather than routed back through
    adapters.build_chat_context, so this test doesn't share a blind spot
    with the code it's meant to be checking against.
    """
    history = [
        _msg("user", "What's the capital of France?"),
        _msg("assistant", "Paris."),
    ]
    user_text = "And Germany?"

    fake_provider = FakeLLMProvider(complete_response="Berlin.")
    result = _manager(fake_provider).chat(history, user_text)

    expected = [
        Message(role="system", content=_CHAT_SYSTEM_PROMPT),
        Message(role="user", content="What's the capital of France?", token_count=10),
        Message(role="assistant", content="Paris.", token_count=10),
        Message(role="user", content=user_text, token_count=HeuristicTokenizer().estimate_tokens(user_text)),
    ]

    sent_messages, _ = fake_provider.complete_calls[0]
    assert sent_messages == expected
    assert result.response == "Berlin."


def test_chat_context_result_matches_strategy_called_directly():
    """
    ChatResult.context (the strategy's own ContextResult) must be
    identical to what PinnedRecencyStrategy.build() returns when called
    directly on the same input -- proving ContextManager doesn't reshape
    or reinterpret the strategy's decision before exposing it.
    """
    history = SCENARIOS["over_budget_forces_pruning"]
    user_text = "one more"

    tokenizer = HeuristicTokenizer()
    wrapped_user = Message(role="user", content=user_text, token_count=tokenizer.estimate_tokens(user_text))
    budget = TokenBudget(max_tokens=Config.MAX_TOKENS, safety_margin=Config.TOKEN_SAFETY_MARGIN)
    expected_result = PinnedRecencyStrategy(recent_buffer=Config.RECENT_BUFFER).build(
        list(history) + [wrapped_user], budget
    )

    fake_provider = FakeLLMProvider(complete_response="reply")
    result = _manager(fake_provider).chat(history, user_text)

    assert result.context == expected_result


def test_system_prompt_is_never_included_in_the_exposed_context_result():
    """
    The system prompt is prepended only for the provider call -- it must
    never appear in ChatResult.context, which reflects only what the
    strategy itself selected (ADR 0004: prompt framing is not a strategy
    decision).
    """
    fake_provider = FakeLLMProvider(complete_response="reply")
    result = _manager(fake_provider).chat([], "hello")

    assert all(m.role != "system" for m in result.context.messages)
    assert all(m.content != _CHAT_SYSTEM_PROMPT for m in result.context.messages)

    # But it IS what actually gets sent to the provider.
    sent_messages, _ = fake_provider.complete_calls[0]
    assert sent_messages[0].role == "system"
    assert sent_messages[0].content == _CHAT_SYSTEM_PROMPT
