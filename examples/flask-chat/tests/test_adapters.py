"""
Tests for adapters.py -- the application-side translation layer between
ORM Message rows and contextshift. No Flask app/client fixture needed:
these functions operate on already-loaded ORM objects and plain
Python/library values, not on live queries or HTTP.
"""
import pytest

import adapters
from config import Config
from conftest import make_message
from contextshift.testing import FakeLLMProvider


def test_to_core_message_maps_fields():
    orm_msg = make_message("user", "hello", token_count=5, is_pinned=True)
    core_msg = adapters.to_core_message(orm_msg)

    assert core_msg.role == "user"
    assert core_msg.content == "hello"
    assert core_msg.token_count == 5
    assert core_msg.is_pinned is True


def test_to_core_messages_preserves_order():
    orm_messages = [make_message("user", f"msg{i}", token_count=1) for i in range(3)]
    core_messages = adapters.to_core_messages(orm_messages)

    assert [m.content for m in core_messages] == ["msg0", "msg1", "msg2"]


def test_build_budget_matches_config():
    budget = adapters.build_budget()
    assert budget.max_tokens == Config.MAX_TOKENS
    assert budget.safety_margin == Config.TOKEN_SAFETY_MARGIN


def test_build_strategy_uses_config_recent_buffer():
    strategy = adapters.build_strategy()
    assert strategy._recent_buffer == Config.RECENT_BUFFER


def test_build_context_manager_prepends_system_message(monkeypatch):
    # build_chat_context was removed in Framework Phase 2 -- this
    # behavior (select context, prepend the system prompt) is now
    # ContextManager's job, reached through build_context_manager().
    fake_provider = FakeLLMProvider(complete_response="reply")
    monkeypatch.setattr(adapters, "build_provider", lambda: fake_provider)

    adapters.build_context_manager().chat([], "hi")

    sent_messages, _ = fake_provider.complete_calls[0]
    assert sent_messages[0].role == "system"
    assert "helpful assistant" in sent_messages[0].content
    assert sent_messages[1].content == "hi"


def test_build_context_manager_applies_strategy_pruning(monkeypatch):
    # Confirms build_context_manager actually routes through
    # PinnedRecencyStrategy -- the pruning behavior itself is
    # characterized directly against the strategy in
    # test_strategies_pinned_recency.py.
    fake_provider = FakeLLMProvider(complete_response="reply")
    monkeypatch.setattr(adapters, "build_provider", lambda: fake_provider)

    candidates = [make_message("user", f"cand{i}", token_count=1000) for i in range(4)]
    recent = [make_message("user", f"recent{i}", token_count=10) for i in range(6)]
    history = adapters.to_core_messages(candidates + recent)

    adapters.build_context_manager().chat(history, "new")

    sent_messages, _ = fake_provider.complete_calls[0]
    contents = [m.content for m in sent_messages[1:]]  # skip the prepended system message

    assert "cand0" not in contents
    assert contents == ["cand1", "cand2", "cand3"] + [f"recent{i}" for i in range(6)] + ["new"]


def test_compute_token_stats_matches_expected_shape():
    orm_messages = [make_message("user", "a", token_count=10), make_message("user", "b", token_count=20)]
    stats = adapters.compute_token_stats(orm_messages)

    assert stats == {
        "current_tokens": 30,
        "max_tokens": Config.MAX_TOKENS,
        "percentage": round(30 / Config.MAX_TOKENS * 100, 2),
    }


def test_build_provider_reads_config_and_requires_api_key(monkeypatch):
    monkeypatch.setattr(Config, "OPENROUTER_API_KEY", "")
    with pytest.raises(ValueError):
        adapters.build_provider()


def test_build_summarizer_wraps_a_provider():
    summarizer = adapters.build_summarizer()
    assert summarizer is not None
    # Constructing one must not raise as long as a real API key is
    # configured (conftest sets OPENROUTER_API_KEY to a dummy non-empty value).
