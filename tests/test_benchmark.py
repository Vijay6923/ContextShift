"""
Tests for contextshift.benchmark: deterministic ContextStrategy
comparison. No network, no LLM, no randomness anywhere in this file --
every assertion is either a hand-traced exact value or a structural
property (ordering, non-mutation) of run_benchmark's own logic.
"""
import csv
import dataclasses
import io
import time

import pytest

from contextshift.benchmark import BenchmarkResult, run_benchmark, to_csv, to_markdown
from contextshift.core import Message, TokenBudget
from contextshift.strategies import ContextResult, PinnedRecencyStrategy, RecencyStrategy, SlidingWindowStrategy

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)  # effective_limit == 3800


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


# -- Metrics correctness -----------------------------------------------------


def test_metrics_are_correct_for_a_hand_traced_scenario():
    # 5 messages at 1000 tokens; SlidingWindowStrategy(window_size=3)
    # keeps the last 3 (3000 tokens, under the 3800 limit) and excludes
    # the first 2 (2000 tokens) purely by count -- no budget pruning
    # needed on top.
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(5)]

    [result] = run_benchmark(messages, BUDGET, [SlidingWindowStrategy(window_size=3)])

    assert result.strategy_name == "SlidingWindowStrategy"
    assert result.messages_kept == 3
    assert result.messages_discarded == 2
    assert result.tokens_kept == 3000
    assert result.tokens_discarded == 2000
    assert result.percentage_retained == 60.0  # 3000 / 5000 * 100


def test_percentage_retained_when_nothing_is_discarded():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(3)]

    [result] = run_benchmark(messages, BUDGET, [RecencyStrategy()])

    assert result.messages_discarded == 0
    assert result.percentage_retained == 100.0


# -- Empty conversations ------------------------------------------------------


def test_empty_conversation_yields_zeroed_metrics_and_full_percentage():
    [result] = run_benchmark([], BUDGET, [RecencyStrategy()])

    assert result.messages_kept == 0
    assert result.messages_discarded == 0
    assert result.tokens_kept == 0
    assert result.tokens_discarded == 0
    # Nothing to lose -- defined as 100%, not a division-by-zero error.
    assert result.percentage_retained == 100.0


def test_empty_conversation_across_all_three_strategies():
    strategies = [RecencyStrategy(), SlidingWindowStrategy(), PinnedRecencyStrategy()]
    results = run_benchmark([], BUDGET, strategies)

    assert len(results) == 3
    assert all(r.messages_kept == 0 and r.messages_discarded == 0 for r in results)


# -- Oversized conversations ---------------------------------------------------


def test_oversized_conversation_does_not_crash_and_prunes_correctly():
    messages = [_msg("user", f"msg{i}", token_count=10) for i in range(5000)]

    [result] = run_benchmark(messages, BUDGET, [SlidingWindowStrategy(window_size=10)])

    assert result.messages_kept == 10
    assert result.messages_discarded == 4990
    assert result.tokens_kept == 100


# -- Identical input across multiple strategies ------------------------------


def test_identical_input_produces_independent_comparable_results():
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(6)]
    strategies = [RecencyStrategy(), SlidingWindowStrategy(window_size=2), PinnedRecencyStrategy(recent_buffer=2)]

    results = run_benchmark(messages, BUDGET, strategies)

    assert [r.strategy_name for r in results] == [
        "RecencyStrategy",
        "SlidingWindowStrategy",
        "PinnedRecencyStrategy",
    ]
    # Each strategy's own policy produces a different kept count for
    # this input -- proves results aren't cross-contaminated or all
    # reflecting whichever strategy ran last.
    assert results[1].messages_kept == 2  # SlidingWindowStrategy: fixed window
    # PinnedRecencyStrategy: recent_buffer=2 (2000 tokens) protected;
    # 4 candidates (4000 tokens) pruned oldest-first until <= 3800,
    # leaving 1 candidate + 2 recent = 3 kept, 3 discarded.
    assert results[2].messages_kept == 3


def test_identical_input_is_not_mutated_across_strategies():
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(6)]
    original = list(messages)
    strategies = [RecencyStrategy(), SlidingWindowStrategy(), PinnedRecencyStrategy()]

    run_benchmark(messages, BUDGET, strategies)

    assert messages == original


# -- Deterministic ordering ---------------------------------------------------


def test_results_are_returned_in_the_same_order_strategies_were_given():
    messages = [_msg("user", "hi", token_count=10)]
    strategies = [PinnedRecencyStrategy(), RecencyStrategy(), SlidingWindowStrategy()]

    results = run_benchmark(messages, BUDGET, strategies)

    assert [r.strategy_name for r in results] == [
        "PinnedRecencyStrategy",
        "RecencyStrategy",
        "SlidingWindowStrategy",
    ]


def test_running_twice_with_the_same_input_produces_identical_results():
    messages = [_msg("user", f"msg{i}", token_count=1000) for i in range(6)]
    strategies = [RecencyStrategy(), SlidingWindowStrategy(), PinnedRecencyStrategy()]

    first = run_benchmark(messages, BUDGET, strategies)
    second = run_benchmark(messages, BUDGET, strategies)

    # Everything except latency (a real wall-clock measurement, not
    # expected to be bit-identical run to run) must match exactly.
    for a, b in zip(first, second):
        assert a.strategy_name == b.strategy_name
        assert a.messages_kept == b.messages_kept
        assert a.messages_discarded == b.messages_discarded
        assert a.tokens_kept == b.tokens_kept
        assert a.tokens_discarded == b.tokens_discarded
        assert a.percentage_retained == b.percentage_retained


# -- Latency ------------------------------------------------------------------


def test_latency_is_measured_as_a_nonnegative_float():
    [result] = run_benchmark([_msg("user", "hi")], BUDGET, [RecencyStrategy()])

    assert isinstance(result.latency_seconds, float)
    assert result.latency_seconds >= 0.0


def test_latency_reflects_the_actual_strategy_call_not_a_constant():
    class SlowStrategy:
        def build(self, messages, budget):
            time.sleep(0.02)
            return ContextResult(messages=list(messages), excluded=[])

    [result] = run_benchmark([_msg("user", "hi")], BUDGET, [SlowStrategy()])

    assert result.latency_seconds >= 0.02


# -- Works with any ContextStrategy-conforming object, not just the three ---
# -- built-in strategies -- proves this module depends on the protocol,   ---
# -- not on any concrete class.                                          ---


def test_works_with_a_duck_typed_strategy_not_a_built_in_class():
    class KeepEverythingStrategy:
        def build(self, messages, budget):
            return ContextResult(messages=list(messages), excluded=[])

    [result] = run_benchmark([_msg("user", "a"), _msg("user", "b")], BUDGET, [KeepEverythingStrategy()])

    assert result.strategy_name == "KeepEverythingStrategy"
    assert result.messages_kept == 2


def test_no_strategies_returns_an_empty_list():
    assert run_benchmark([_msg("user", "hi")], BUDGET, []) == []


# -- CSV export -----------------------------------------------------------


def test_to_csv_round_trips_through_the_standard_csv_reader():
    results = run_benchmark(
        [_msg("user", f"msg{i}", token_count=1000) for i in range(6)],
        BUDGET,
        [RecencyStrategy(), SlidingWindowStrategy()],
    )

    csv_text = to_csv(results)
    rows = list(csv.reader(io.StringIO(csv_text)))

    assert rows[0] == [
        "strategy_name",
        "messages_kept",
        "messages_discarded",
        "tokens_kept",
        "tokens_discarded",
        "percentage_retained",
        "latency_seconds",
    ]
    assert rows[1][0] == "RecencyStrategy"
    assert rows[2][0] == "SlidingWindowStrategy"
    assert len(rows) == 3  # header + 2 results


def test_to_csv_of_empty_results_is_just_the_header():
    csv_text = to_csv([])
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert len(rows) == 1


# -- Markdown export --------------------------------------------------------


def test_to_markdown_produces_a_table_with_header_separator_and_one_row_per_result():
    results = run_benchmark(
        [_msg("user", f"msg{i}", token_count=1000) for i in range(3)],
        BUDGET,
        [RecencyStrategy()],
    )

    markdown = to_markdown(results)
    lines = markdown.splitlines()

    assert lines[0].startswith("| Strategy |")
    assert lines[1].startswith("| --- |")
    assert len(lines) == 3  # header + separator + 1 result row
    assert "RecencyStrategy" in lines[2]


def test_to_markdown_of_empty_results_is_header_and_separator_only():
    markdown = to_markdown([])
    assert len(markdown.splitlines()) == 2


# -- BenchmarkResult is a plain, inspectable value type ----------------------


def test_benchmark_result_is_a_frozen_dataclass():
    result = BenchmarkResult(
        strategy_name="X",
        messages_kept=1,
        messages_discarded=0,
        tokens_kept=10,
        tokens_discarded=0,
        percentage_retained=100.0,
        latency_seconds=0.0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.messages_kept = 2
