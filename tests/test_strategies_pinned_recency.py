"""
Direct behavioral tests of PinnedRecencyStrategy against the new
ContextStrategy interface. These mirror the scenarios already
characterized against the legacy algorithm in test_context_builder.py
(untouched, still passing, still exercising utils/context_builder.py) --
this file asserts the same outcomes are reachable through the new
interface, plus a few cases specific to the new, configurable
`recent_buffer` and the new `excluded` field that legacy has no
equivalent for.
"""
import pytest

from contextshift.core import Message, TokenBudget
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)  # effective_limit == 3800


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def _contents(messages):
    return [m.content for m in messages]


def test_under_budget_keeps_everything_in_order_and_excludes_nothing():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(3)]
    result = PinnedRecencyStrategy().build(messages, BUDGET)

    assert _contents(result.messages) == ["msg0", "msg1", "msg2"]
    assert result.excluded == []


def test_single_oldest_candidate_pruned_when_barely_over_budget():
    candidates = [_msg("user", f"cand{i}", token_count=1000) for i in range(4)]
    recent = [_msg("user", f"recent{i}", token_count=10) for i in range(6)]

    result = PinnedRecencyStrategy().build(candidates + recent, BUDGET)

    assert _contents(result.messages) == ["cand1", "cand2", "cand3"] + [f"recent{i}" for i in range(6)]
    assert _contents(result.excluded) == ["cand0"]


def test_multiple_candidates_pruned_oldest_first_and_recorded_in_excluded():
    candidates = [_msg("user", f"cand{i}", token_count=2000) for i in range(4)]
    recent = [_msg("user", f"recent{i}", token_count=10) for i in range(6)]

    result = PinnedRecencyStrategy().build(candidates + recent, BUDGET)

    assert _contents(result.messages) == ["cand3"] + [f"recent{i}" for i in range(6)]
    assert _contents(result.excluded) == ["cand0", "cand1", "cand2"]


def test_recent_pruning_only_starts_after_all_candidates_exhausted():
    recent = [_msg("user", f"recent{i}", token_count=1000) for i in range(6)]
    result = PinnedRecencyStrategy().build(recent, BUDGET)

    assert _contents(result.messages) == ["recent3", "recent4", "recent5"]
    assert _contents(result.excluded) == ["recent0", "recent1", "recent2"]


def test_recent_pruning_never_drops_the_last_message_even_if_still_over_budget():
    recent = [_msg("user", f"recent{i}", token_count=10000) for i in range(6)]
    result = PinnedRecencyStrategy().build(recent, BUDGET)

    assert _contents(result.messages) == ["recent5"]
    assert _contents(result.excluded) == [f"recent{i}" for i in range(5)]


def test_pinned_messages_survive_both_pruning_stages():
    pinned = _msg("system", "pinned instruction", token_count=5000, is_pinned=True)
    candidates = [_msg("user", f"cand{i}", token_count=10) for i in range(4)]
    recent = [_msg("user", f"recent{i}", token_count=10) for i in range(6)]

    result = PinnedRecencyStrategy().build([pinned] + candidates + recent, BUDGET)

    assert _contents(result.messages) == ["pinned instruction", "recent5"]


def test_pinned_placed_before_candidates_and_recent_when_no_pruning_needed():
    pinned = _msg("system", "pinned", token_count=10, is_pinned=True)
    candidate = _msg("user", "candidate", token_count=10)
    recent = [_msg("user", f"recent{i}", token_count=10) for i in range(6)]

    result = PinnedRecencyStrategy().build([pinned, candidate] + recent, BUDGET)

    assert _contents(result.messages) == ["pinned", "candidate"] + [f"recent{i}" for i in range(6)]


def test_empty_input_returns_empty_result():
    result = PinnedRecencyStrategy().build([], BUDGET)
    assert result.messages == []
    assert result.excluded == []


# -- New capability: recent_buffer is now configurable (was a hardcoded
# Config constant in the legacy implementation). --


def test_recent_buffer_is_configurable():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(5)]
    result = PinnedRecencyStrategy(recent_buffer=3).build(messages, BUDGET)

    # With a 3-message recency window, msg0/msg1 are candidates and would
    # be pruned first if over budget; here nothing is over budget, so
    # everything is still kept -- this only confirms the smaller window
    # doesn't change well-under-budget behavior.
    assert _contents(result.messages) == [f"msg{i}" for i in range(5)]


def test_recent_buffer_of_one_still_protects_the_single_most_recent_message():
    messages = [_msg("user", f"msg{i}", token_count=10000) for i in range(3)]
    result = PinnedRecencyStrategy(recent_buffer=1).build(messages, BUDGET)

    assert _contents(result.messages) == ["msg2"]


@pytest.mark.parametrize("recent_buffer", [0, -1])
def test_recent_buffer_below_one_is_rejected(recent_buffer):
    with pytest.raises(ValueError, match="recent_buffer"):
        PinnedRecencyStrategy(recent_buffer=recent_buffer)
