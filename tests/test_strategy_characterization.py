"""
Direct comparison between the legacy utils.context_builder.build_context
(still what the running application uses) and the new
contextshift.strategies.pinned_recency.PinnedRecencyStrategy, run against
the exact same Message objects for each scenario.

contextshift.core.Message duck-types cleanly against what the legacy
function actually reads (.role, .content, .is_pinned, and, via
token_manager, .token_count) -- so the same instances are fed to both
implementations directly, with no separate translation layer that could
introduce its own bugs into the comparison.

The new strategy deliberately does not prepend a system message or
produce OpenAI-format dicts (see
docs/decisions/0004-context-strategy-interface.md for why that's scoped
out of ContextResult). To prove the underlying selection algorithm is
unchanged despite that shape difference, each case reconstructs the
legacy shape from the new result -- prepend the same hardcoded system
message, convert Message to the same {"role", "content"} dict shape --
and asserts full equality against the legacy function's real output.

This is the "confidence before cutover" check Step 4 was explicitly
asked for: not just that the new code has its own passing tests, but
that it produces the identical selection as the code still running in
production, on the same inputs.
"""
import pytest

from config import Config
from contextshift.core import Message, TokenBudget
from contextshift.strategies.pinned_recency import PinnedRecencyStrategy
from utils import context_builder as legacy

# Copied verbatim from utils/context_builder.py -- deliberately duplicated
# here rather than imported, since owning this exact string is precisely
# what the new strategy does NOT do (see ADR 0004). Duplicating it is what
# lets this test prove the two implementations agree on selection while
# disagreeing, by design, on formatting.
_LEGACY_SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a helpful assistant. The conversation history below may "
        "include a summary of earlier messages."
    ),
}


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


SCENARIOS = {
    "empty_conversation": [],
    "under_budget_passthrough": [_msg("user", f"msg{i}", token_count=10) for i in range(3)],
    "single_candidate_pruned": (
        [_msg("user", f"cand{i}", token_count=1000) for i in range(4)]
        + [_msg("user", f"recent{i}", token_count=10) for i in range(6)]
    ),
    "multiple_candidates_pruned": (
        [_msg("user", f"cand{i}", token_count=2000) for i in range(4)]
        + [_msg("user", f"recent{i}", token_count=10) for i in range(6)]
    ),
    "recent_pruned_after_candidates_exhausted": [
        _msg("user", f"recent{i}", token_count=1000) for i in range(6)
    ],
    "recent_never_drops_last_message": [
        _msg("user", f"recent{i}", token_count=10000) for i in range(6)
    ],
    "pinned_survives_both_pruning_stages": (
        [_msg("system", "pinned instruction", token_count=5000, is_pinned=True)]
        + [_msg("user", f"cand{i}", token_count=10) for i in range(4)]
        + [_msg("user", f"recent{i}", token_count=10) for i in range(6)]
    ),
    "pinned_before_candidates_and_recent_no_pruning": (
        [_msg("system", "pinned", token_count=10, is_pinned=True)]
        + [_msg("user", "candidate", token_count=10)]
        + [_msg("user", f"recent{i}", token_count=10) for i in range(6)]
    ),
    "single_message": [_msg("user", "hello", token_count=10)],
    "exactly_six_non_pinned_no_pruning": [
        _msg("user", f"msg{i}", token_count=10) for i in range(6)
    ],
    "seven_non_pinned_one_candidate_under_budget": [
        _msg("user", f"msg{i}", token_count=10) for i in range(7)
    ],
    "realistic_mixed_conversation": (
        [_msg("system", "Always answer in French.", token_count=8, is_pinned=True)]
        + [
            _msg("user", "What's the capital of France?", token_count=9),
            _msg("assistant", "Paris.", token_count=3),
            _msg("user", "And Germany?", token_count=5),
            _msg("assistant", "Berlin.", token_count=3),
        ]
        + [_msg("user", f"follow up question {i}", token_count=12) for i in range(6)]
    ),
}


@pytest.mark.parametrize("messages", SCENARIOS.values(), ids=SCENARIOS.keys())
def test_new_strategy_selection_matches_legacy_exactly(messages):
    legacy_result = legacy.build_context(messages)

    strategy = PinnedRecencyStrategy(recent_buffer=Config.RECENT_BUFFER)
    budget = TokenBudget(max_tokens=Config.MAX_TOKENS, safety_margin=Config.TOKEN_SAFETY_MARGIN)
    new_result = strategy.build(messages, budget)

    reconstructed_legacy_shape = [_LEGACY_SYSTEM_MESSAGE] + [
        {"role": m.role, "content": m.content} for m in new_result.messages
    ]

    assert legacy_result == reconstructed_legacy_shape
