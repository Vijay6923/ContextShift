"""
Direct behavioral tests of RecencyStrategy, plus a characterization-
style equivalence check against PinnedRecencyStrategy(recent_buffer=1).

No legacy implementation exists to characterize against (this is a new
strategy, not a port, same situation as SlidingWindowStrategy -- see
docs/decisions/0012-strategy-framework-and-benchmark-review.md, Section
2). In its place, the scenarios below assert exact, hand-traced
expected output, and a separate section proves -- rather than asserts
in passing -- the specific relationship to an existing strategy
documented in RecencyStrategy's own docstring: for unpinned input, it
selects the identical trailing suffix PinnedRecencyStrategy(recent_buffer=1)
does. That's a real architectural fact about this framework's design
space, not a coincidence to leave unverified.
"""
import pytest

from contextshift.core import Message, TokenBudget
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy
from contextshift.strategies.recency import RecencyStrategy

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)  # effective_limit == 3800


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def _contents(messages):
    return [m.content for m in messages]


def test_under_budget_keeps_everything_in_order_and_excludes_nothing():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(5)]
    result = RecencyStrategy().build(messages, BUDGET)

    assert _contents(result.messages) == [f"msg{i}" for i in range(5)]
    assert result.excluded == []


def test_over_budget_prunes_oldest_first():
    # 3800 effective limit; 5 messages at 1000 tokens each = 5000 total.
    # Prune oldest until <= 3800: drop msg0 (4000), drop msg1 (3000) -> fits.
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(5)]
    result = RecencyStrategy().build(messages, BUDGET)

    assert _contents(result.messages) == ["msg2", "msg3", "msg4"]
    assert _contents(result.excluded) == ["msg0", "msg1"]


def test_never_drops_the_last_message_even_if_still_over_budget():
    messages = [_msg("user", f"msg{i}", token_count=10000) for i in range(4)]
    result = RecencyStrategy().build(messages, BUDGET)

    assert _contents(result.messages) == ["msg3"]
    assert _contents(result.excluded) == ["msg0", "msg1", "msg2"]


def test_pinned_messages_are_pruned_anyway_no_pinning_support():
    # The core, deliberate difference from PinnedRecencyStrategy:
    # is_pinned is never consulted.
    pinned = _msg("system", "pinned instruction", token_count=1000, is_pinned=True)
    filler = [_msg("user", f"filler{i}", token_count=1000) for i in range(4)]

    result = RecencyStrategy().build([pinned] + filler, BUDGET)

    assert "pinned instruction" not in _contents(result.messages)
    assert "pinned instruction" in _contents(result.excluded)


def test_pinned_message_survives_only_because_its_recent():
    pinned = _msg("system", "pinned", token_count=10, is_pinned=True)
    result = RecencyStrategy().build([pinned], BUDGET)

    assert _contents(result.messages) == ["pinned"]


def test_empty_input_returns_empty_result():
    result = RecencyStrategy().build([], BUDGET)
    assert result.messages == []
    assert result.excluded == []


def test_takes_no_configuration():
    # Deliberately no constructor argument -- see the class docstring.
    # This just confirms the zero-arg constructor actually works.
    strategy = RecencyStrategy()
    result = strategy.build([_msg("user", "hi")], BUDGET)
    assert _contents(result.messages) == ["hi"]


def test_history_is_not_mutated():
    messages = [_msg("user", f"msg{i}", token_count=10000) for i in range(5)]
    original = list(messages)

    RecencyStrategy().build(messages, BUDGET)

    assert messages == original


# -- Equivalence to PinnedRecencyStrategy(recent_buffer=1), unpinned --------
#
# Documented explicitly in RecencyStrategy's own docstring: for input
# with no pinned messages, both strategies select the identical
# trailing suffix. Proven here across several scenarios, not just
# claimed.


EQUIVALENCE_SCENARIOS = {
    "empty": [],
    "single_message": [_msg("user", "hello", token_count=10)],
    "well_under_budget": [_msg("user", f"msg{i}", token_count=10) for i in range(5)],
    "requires_pruning": [_msg("user", f"msg{i}", token_count=1000) for i in range(6)],
    "single_message_exceeds_budget_alone": [_msg("user", "huge", token_count=50000)],
    "many_small_messages": [_msg("user", f"msg{i}", token_count=5) for i in range(50)],
    "realistic_mixed_conversation": [
        _msg("user", "What's the capital of France?", token_count=9),
        _msg("assistant", "Paris.", token_count=3),
        _msg("user", "And Germany?", token_count=5),
        _msg("assistant", "Berlin.", token_count=3),
    ]
    + [_msg("user", f"follow up question {i}", token_count=1200) for i in range(6)],
}


@pytest.mark.parametrize("messages", EQUIVALENCE_SCENARIOS.values(), ids=EQUIVALENCE_SCENARIOS.keys())
def test_matches_pinned_recency_strategy_with_recent_buffer_of_one(messages):
    recency_result = RecencyStrategy().build(messages, BUDGET)
    pinned_recency_result = PinnedRecencyStrategy(recent_buffer=1).build(messages, BUDGET)

    assert recency_result.messages == pinned_recency_result.messages
    assert recency_result.excluded == pinned_recency_result.excluded
