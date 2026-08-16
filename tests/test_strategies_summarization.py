"""
Direct behavioral tests of SummarizationStrategy.

Unlike RecencyStrategy/SlidingWindowStrategy, this strategy calls a
Summarizer (which calls an LLMProvider) inside build() -- every test
here uses contextshift.testing.FakeSummarizer so the suite stays
network-free and deterministic, the same reason FakeLLMProvider exists
for anything depending on LLMProvider directly.
"""
import pytest

from contextshift.core import Message, TokenBudget
from contextshift.strategies.summarization_strategy import SummarizationStrategy
from contextshift.testing import FakeSummarizer
from contextshift.tokenizers.heuristic import HeuristicTokenizer

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)  # effective_limit == 3800


def _msg(role, content, token_count=10):
    return Message(role=role, content=content, token_count=token_count)


def _contents(messages):
    return [m.content for m in messages]


def test_short_history_skips_summarization_and_keeps_everything():
    # len(messages) <= keep_recent -> nothing to summarize.
    messages = [_msg("user", f"msg{i}") for i in range(3)]
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=6)
    result = strategy.build(messages, BUDGET)

    assert _contents(result.messages) == [f"msg{i}" for i in range(3)]
    assert result.excluded == []


def test_older_messages_are_replaced_by_a_single_summary_message():
    messages = [_msg("user", f"msg{i}") for i in range(10)]
    strategy = SummarizationStrategy(
        FakeSummarizer("[FAKE SUMMARY]"), HeuristicTokenizer(), keep_recent=4
    )
    result = strategy.build(messages, BUDGET)

    # 1 summary message + 4 recent, verbatim, in order.
    assert result.messages[0].content == "[FAKE SUMMARY]"
    assert result.messages[0].role == "system"
    assert _contents(result.messages[1:]) == ["msg6", "msg7", "msg8", "msg9"]


def test_summarized_messages_are_reported_as_excluded():
    messages = [_msg("user", f"msg{i}") for i in range(10)]
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=4)
    result = strategy.build(messages, BUDGET)

    assert _contents(result.excluded) == [f"msg{i}" for i in range(6)]


def test_summary_token_count_is_measured_by_the_given_tokenizer():
    messages = [_msg("user", f"msg{i}") for i in range(10)]
    tokenizer = HeuristicTokenizer()
    summary_text = "one two three four five"
    strategy = SummarizationStrategy(FakeSummarizer(summary_text), tokenizer, keep_recent=4)
    result = strategy.build(messages, BUDGET)

    assert result.messages[0].token_count == tokenizer.estimate_tokens(summary_text)


def test_recent_window_is_pruned_further_if_summary_plus_recent_exceeds_budget():
    # Summary (huge) + 4 recent messages at 2000 tokens each blows past
    # the 3800 effective limit; the recent window is pruned oldest-first
    # until it fits, same discipline as every other strategy's pruning.
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(6)] + [
        _msg("user", f"recent{i}", token_count=2000) for i in range(4)
    ]

    class _HugeTokenizer:
        def estimate_tokens(self, text):
            return 3000

    strategy = SummarizationStrategy(FakeSummarizer(), _HugeTokenizer(), keep_recent=4)
    result = strategy.build(messages, BUDGET)

    # summary (3000) + recent0 (2000) = 5000 > 3800 -> drop recent0.
    # summary (3000) + recent1 (2000) = 5000 > 3800 -> drop recent1.
    # summary (3000) + recent2 (2000) = 5000 > 3800 -> drop recent2.
    # summary (3000) + recent3 (2000) = 5000 > 3800, but only one message
    # left in the recent window -> stop, never drop the last one.
    assert _contents(result.messages) == ["[FAKE SUMMARY]", "recent3"]
    assert "recent0" in _contents(result.excluded)
    assert "recent1" in _contents(result.excluded)
    assert "recent2" in _contents(result.excluded)


def test_summarize_older_false_falls_back_to_plain_oldest_first_pruning():
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(6)]
    strategy = SummarizationStrategy(
        FakeSummarizer(), HeuristicTokenizer(), keep_recent=2, summarize_older=False
    )
    result = strategy.build(messages, BUDGET)

    # No summary message anywhere; plain pruning down to fit 3800:
    # 6000 total -> drop msg0 (5000), msg1 (4000), msg2 (3000) -> fits.
    assert "[FAKE SUMMARY]" not in _contents(result.messages)
    assert _contents(result.messages) == ["msg3", "msg4", "msg5"]
    assert _contents(result.excluded) == ["msg0", "msg1", "msg2"]


def test_under_budget_history_with_summarize_older_false_keeps_everything():
    messages = [_msg("user", f"msg{i}") for i in range(5)]
    strategy = SummarizationStrategy(
        FakeSummarizer(), HeuristicTokenizer(), keep_recent=6, summarize_older=False
    )
    result = strategy.build(messages, BUDGET)

    assert _contents(result.messages) == [f"msg{i}" for i in range(5)]
    assert result.excluded == []


def test_keep_recent_less_than_one_raises():
    with pytest.raises(ValueError, match="keep_recent"):
        SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=0)


def test_empty_input_returns_empty_result():
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer())
    result = strategy.build([], BUDGET)

    assert result.messages == []
    assert result.excluded == []


def test_history_is_not_mutated():
    messages = [_msg("user", f"msg{i}") for i in range(10)]
    original = list(messages)
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=4)

    strategy.build(messages, BUDGET)

    assert messages == original


def test_summarizer_receives_only_the_older_messages_not_the_recent_ones():
    messages = [_msg("user", f"msg{i}") for i in range(10)]
    fake = FakeSummarizer()
    strategy = SummarizationStrategy(fake, HeuristicTokenizer(), keep_recent=4)

    strategy.build(messages, BUDGET)

    # FakeSummarizer -> Summarizer.summarize -> provider.complete; the
    # underlying FakeLLMProvider recorded exactly one call.
    assert len(fake._provider.complete_calls) == 1
    sent_messages, _ = fake._provider.complete_calls[0]
    # Summarizer wraps the conversation into a single user-role prompt
    # message (plus a system prompt) -- assert the six older messages'
    # content made it into that prompt, and the four recent ones didn't.
    prompt_text = sent_messages[-1].content
    for i in range(6):
        assert f"msg{i}" in prompt_text
    for i in range(6, 10):
        assert f"msg{i}" not in prompt_text


def test_conforms_to_context_strategy_protocol():
    from contextshift.strategies.base import ContextStrategy

    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer())
    assert isinstance(strategy, ContextStrategy)
