"""
Direct behavioral tests of SlidingWindowStrategy.

No legacy implementation exists to characterize against (unlike
PinnedRecencyStrategy, which was ported from tests/fixtures/legacy/context_builder.py)
-- this is a new strategy, not a port, per
docs/decisions/0012-strategy-framework-and-benchmark-review.md (Section
2). In place of a legacy comparison, the scenarios below assert exact,
hand-traced expected output for each case -- the same "prove the exact
value, don't just assert a property" discipline characterization tests
apply elsewhere in this project, applied here without a second
implementation to compare against.
"""
import pytest

from contextshift.core import Message, TokenBudget
from contextshift.strategies.sliding_window import SlidingWindowStrategy

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)  # effective_limit == 3800


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def _contents(messages):
    return [m.content for m in messages]


def test_fewer_messages_than_window_keeps_everything():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(3)]
    result = SlidingWindowStrategy(window_size=6).build(messages, BUDGET)

    assert _contents(result.messages) == ["msg0", "msg1", "msg2"]
    assert result.excluded == []


def test_exactly_window_size_messages_keeps_everything():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(6)]
    result = SlidingWindowStrategy(window_size=6).build(messages, BUDGET)

    assert _contents(result.messages) == [f"msg{i}" for i in range(6)]
    assert result.excluded == []


def test_more_messages_than_window_excludes_the_oldest_by_count():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(9)]
    result = SlidingWindowStrategy(window_size=6).build(messages, BUDGET)

    assert _contents(result.messages) == [f"msg{i}" for i in range(3, 9)]
    assert _contents(result.excluded) == ["msg0", "msg1", "msg2"]


def test_window_still_over_budget_prunes_oldest_of_the_window_next():
    # 6 messages fit the window, but at 1000 tokens each (6000 total)
    # they don't fit the 3800-token effective budget -- the three oldest
    # of the window must be pruned on top of the count-based selection
    # (1000*3 = 3000 fits; 1000*4 = 4000 does not).
    older = [_msg("user", f"older{i}", token_count=10) for i in range(3)]
    windowed = [_msg("user", f"win{i}", token_count=1000) for i in range(6)]

    result = SlidingWindowStrategy(window_size=6).build(older + windowed, BUDGET)

    assert _contents(result.messages) == ["win3", "win4", "win5"]
    # Chronological order preserved: count-excluded (older) before
    # budget-excluded (win0, win1, win2), matching ContextResult's contract.
    assert _contents(result.excluded) == ["older0", "older1", "older2", "win0", "win1", "win2"]


def test_never_drops_the_last_message_even_if_still_over_budget():
    messages = [_msg("user", f"msg{i}", token_count=10000) for i in range(6)]
    result = SlidingWindowStrategy(window_size=6).build(messages, BUDGET)

    assert _contents(result.messages) == ["msg5"]
    assert _contents(result.excluded) == [f"msg{i}" for i in range(5)]


def test_pinned_messages_outside_the_window_are_excluded_anyway():
    # No pinning support, by design (ADR 0012 Section 2) -- unlike
    # PinnedRecencyStrategy, is_pinned is not consulted at all.
    pinned = _msg("system", "pinned instruction", token_count=10, is_pinned=True)
    recent = [_msg("user", f"recent{i}", token_count=10) for i in range(6)]

    result = SlidingWindowStrategy(window_size=6).build([pinned] + recent, BUDGET)

    assert "pinned instruction" not in _contents(result.messages)
    assert "pinned instruction" in _contents(result.excluded)


def test_pinned_message_inside_the_window_is_kept_only_because_its_recent():
    # Confirms pinning has no special effect even when the pinned
    # message happens to survive -- it survives by recency, not by
    # is_pinned.
    pinned = _msg("system", "pinned", token_count=10000, is_pinned=True)
    result = SlidingWindowStrategy(window_size=1).build([pinned], BUDGET)

    # Floor-of-one keeps it, same as any other single message would be kept.
    assert _contents(result.messages) == ["pinned"]


def test_empty_input_returns_empty_result():
    result = SlidingWindowStrategy().build([], BUDGET)
    assert result.messages == []
    assert result.excluded == []


def test_window_size_is_configurable():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(5)]
    result = SlidingWindowStrategy(window_size=2).build(messages, BUDGET)

    assert _contents(result.messages) == ["msg3", "msg4"]
    assert _contents(result.excluded) == ["msg0", "msg1", "msg2"]


def test_window_size_of_one_still_protects_the_single_most_recent_message():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(3)]
    result = SlidingWindowStrategy(window_size=1).build(messages, BUDGET)

    assert _contents(result.messages) == ["msg2"]
    assert _contents(result.excluded) == ["msg0", "msg1"]


@pytest.mark.parametrize("window_size", [0, -1])
def test_window_size_below_one_is_rejected(window_size):
    with pytest.raises(ValueError, match="window_size"):
        SlidingWindowStrategy(window_size=window_size)


def test_history_is_not_mutated():
    messages = [_msg("user", f"msg{i}", token_count=10000) for i in range(9)]
    original = list(messages)

    SlidingWindowStrategy(window_size=6).build(messages, BUDGET)

    assert messages == original
