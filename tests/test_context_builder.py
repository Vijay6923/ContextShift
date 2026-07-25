"""
Direct, DB-free characterization of utils.context_builder.build_context --
the algorithm Step 4 of the migration will port. None of the HTTP-level
tests actually inspect what context gets assembled (they mock the LLM call
and ignore its `messages` argument), so this file is the only thing that
would catch a regression in the pin/recency/pruning logic itself.
"""
from conftest import make_message
from utils import context_builder


def _contents(result):
    return [m["content"] for m in result[1:]]  # drop the prepended system message


def test_system_message_is_always_prepended():
    result = context_builder.build_context([])
    assert result[0]["role"] == "system"
    assert "helpful assistant" in result[0]["content"]


def test_under_budget_conversation_keeps_everything_in_order():
    messages = [make_message("user", f"msg{i}", token_count=10) for i in range(3)]
    result = context_builder.build_context(messages)
    assert _contents(result) == ["msg0", "msg1", "msg2"]


def test_single_oldest_candidate_pruned_when_barely_over_budget():
    candidates = [make_message("user", f"cand{i}", token_count=1000) for i in range(4)]
    recent = [make_message("user", f"recent{i}", token_count=10) for i in range(6)]

    result = context_builder.build_context(candidates + recent)

    assert _contents(result) == ["cand1", "cand2", "cand3"] + [f"recent{i}" for i in range(6)]


def test_multiple_candidates_pruned_oldest_first_until_under_budget():
    candidates = [make_message("user", f"cand{i}", token_count=2000) for i in range(4)]
    recent = [make_message("user", f"recent{i}", token_count=10) for i in range(6)]

    result = context_builder.build_context(candidates + recent)

    assert _contents(result) == ["cand3"] + [f"recent{i}" for i in range(6)]


def test_recent_pruning_only_starts_after_all_candidates_exhausted():
    # Exactly 6 non-pinned messages -> zero candidates, all 6 are "recent".
    recent = [make_message("user", f"recent{i}", token_count=1000) for i in range(6)]

    result = context_builder.build_context(recent)

    assert _contents(result) == ["recent3", "recent4", "recent5"]


def test_recent_pruning_never_drops_the_last_message_even_if_still_over_budget():
    recent = [make_message("user", f"recent{i}", token_count=10000) for i in range(6)]

    result = context_builder.build_context(recent)

    assert _contents(result) == ["recent5"]


def test_pinned_messages_survive_both_pruning_stages():
    pinned = make_message("system", "pinned instruction", token_count=5000, is_pinned=True)
    candidates = [make_message("user", f"cand{i}", token_count=10) for i in range(4)]
    recent = [make_message("user", f"recent{i}", token_count=10) for i in range(6)]

    result = context_builder.build_context([pinned] + candidates + recent)
    contents = _contents(result)

    assert contents == ["pinned instruction", "recent5"]


def test_pinned_placed_before_candidates_and_recent_when_no_pruning_needed():
    pinned = make_message("system", "pinned", token_count=10, is_pinned=True)
    candidate = make_message("user", "candidate", token_count=10)
    recent = [make_message("user", f"recent{i}", token_count=10) for i in range(6)]

    result = context_builder.build_context([pinned, candidate] + recent)

    assert _contents(result) == ["pinned", "candidate"] + [f"recent{i}" for i in range(6)]
