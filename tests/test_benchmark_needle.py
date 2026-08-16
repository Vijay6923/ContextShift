"""Tests for contextshift.benchmark.needle: needle-retention evaluation."""
import pytest

from contextshift.benchmark.needle import ProbeOutcome, evaluate_fixture, run_needle_benchmark
from contextshift.benchmark.probes import ConversationFixture, Probe
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy, RecencyStrategy, SlidingWindowStrategy
from contextshift.strategies.base import ContextResult

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)


def _msg(role, content, token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def _fixture(name, messages, probes):
    return ConversationFixture(
        name=name, failure_mode="test", description="d", messages=tuple(messages), probes=tuple(probes)
    )


# -- evaluate_fixture ---------------------------------------------------


def test_evaluate_fixture_all_load_bearing_messages_retained():
    m0, m1, m2 = _msg("user", "a"), _msg("user", "b"), _msg("user", "c")
    fixture = _fixture("f", [m0, m1, m2], [Probe(question="q", load_bearing_indices=(0, 2))])

    [outcome] = evaluate_fixture(fixture, kept=[m0, m1, m2])

    assert outcome.satisfied is True
    assert outcome.retained_count == 2
    assert outcome.total_count == 2


def test_evaluate_fixture_partial_retention_is_not_satisfied():
    m0, m1 = _msg("user", "a"), _msg("user", "b")
    fixture = _fixture("f", [m0, m1], [Probe(question="q", load_bearing_indices=(0, 1))])

    [outcome] = evaluate_fixture(fixture, kept=[m0])  # m1 dropped

    assert outcome.satisfied is False
    assert outcome.retained_count == 1
    assert outcome.total_count == 2


def test_evaluate_fixture_uses_identity_not_value_equality():
    # Two messages with identical content/role/token_count -- only one
    # of them (by identity) is actually "kept". Value equality would
    # incorrectly count the probe as satisfied.
    original = _msg("user", "duplicate content", token_count=10)
    lookalike = _msg("user", "duplicate content", token_count=10)
    assert original == lookalike  # same value, different objects

    fixture = _fixture("f", [original], [Probe(question="q", load_bearing_indices=(0,))])

    outcome = evaluate_fixture(fixture, kept=[lookalike])[0]
    assert outcome.satisfied is False

    outcome2 = evaluate_fixture(fixture, kept=[original])[0]
    assert outcome2.satisfied is True


def test_evaluate_fixture_with_no_probes_returns_empty_list():
    fixture = _fixture("f", [_msg("user", "a")], [])
    assert evaluate_fixture(fixture, kept=[]) == []


# -- run_needle_benchmark -------------------------------------------------


def test_run_needle_benchmark_requires_at_least_one_fixture():
    with pytest.raises(ValueError, match="at least one fixture"):
        run_needle_benchmark([], BUDGET, [RecencyStrategy()])


def test_run_needle_benchmark_reports_full_retention_when_strategy_keeps_everything():
    messages = [_msg("user", f"m{i}", token_count=5) for i in range(3)]
    fixture = _fixture("f", messages, [Probe(question="q", load_bearing_indices=(0, 1, 2))])

    [result] = run_needle_benchmark([fixture], BUDGET, [RecencyStrategy()])

    assert result.strategy_name == "RecencyStrategy"
    assert result.needle_retention == 100.0
    assert result.probes_satisfied == "1 / 1"


def test_run_needle_benchmark_detects_a_dropped_needle():
    # A sliding window of 1 keeps only the last message -- the probe
    # needs the first one, so it must fail.
    messages = [_msg("user", f"m{i}", token_count=5) for i in range(5)]
    fixture = _fixture("f", messages, [Probe(question="q", load_bearing_indices=(0,))])

    [result] = run_needle_benchmark([fixture], BUDGET, [SlidingWindowStrategy(window_size=1)])

    assert result.needle_retention == 0.0
    assert result.probes_satisfied == "0 / 1"


def test_run_needle_benchmark_aggregates_across_multiple_fixtures():
    messages_a = [_msg("user", f"a{i}", token_count=5) for i in range(3)]
    messages_b = [_msg("user", f"b{i}", token_count=5) for i in range(3)]
    fixture_a = _fixture("a", messages_a, [Probe(question="q", load_bearing_indices=(0,))])
    fixture_b = _fixture("b", messages_b, [Probe(question="q", load_bearing_indices=(0,))])

    # window_size=1: only the last message of each fixture survives, so
    # neither probe (which needs index 0) is satisfied.
    [result] = run_needle_benchmark([fixture_a, fixture_b], BUDGET, [SlidingWindowStrategy(window_size=1)])

    assert result.probes_satisfied == "0 / 2"
    assert result.messages_kept == 2  # 1 kept per fixture, 2 fixtures


def test_run_needle_benchmark_preserves_strategy_order():
    messages = [_msg("user", "a", token_count=5)]
    fixture = _fixture("f", messages, [])

    results = run_needle_benchmark(
        [fixture], BUDGET, [PinnedRecencyStrategy(), RecencyStrategy(), SlidingWindowStrategy()]
    )

    assert [r.strategy_name for r in results] == [
        "PinnedRecencyStrategy",
        "RecencyStrategy",
        "SlidingWindowStrategy",
    ]


def test_run_needle_benchmark_with_zero_probes_reports_full_retention():
    # No probes to fail -- vacuously 100%, matching total_tokens()'s own
    # "nothing to lose" convention for the empty case.
    fixture = _fixture("f", [_msg("user", "a", token_count=5)], [])

    [result] = run_needle_benchmark([fixture], BUDGET, [RecencyStrategy()])

    assert result.needle_retention == 100.0
    assert result.probes_satisfied == "0 / 0"


def test_run_needle_benchmark_does_not_mutate_fixture_messages():
    messages = [_msg("user", f"m{i}", token_count=5) for i in range(3)]
    fixture = _fixture("f", messages, [Probe(question="q", load_bearing_indices=(0,))])
    original = list(fixture.messages)

    run_needle_benchmark([fixture], BUDGET, [RecencyStrategy(), SlidingWindowStrategy()])

    assert list(fixture.messages) == original


def test_probe_outcome_satisfied_property():
    probe = Probe(question="q", load_bearing_indices=(0, 1))
    assert ProbeOutcome(fixture_name="f", probe=probe, retained_count=2, total_count=2).satisfied is True
    assert ProbeOutcome(fixture_name="f", probe=probe, retained_count=1, total_count=2).satisfied is False


def test_works_with_a_duck_typed_strategy():
    class KeepEverythingStrategy:
        def build(self, messages, budget):
            return ContextResult(messages=list(messages), excluded=[])

    fixture = _fixture(
        "f", [_msg("user", "a", token_count=5)], [Probe(question="q", load_bearing_indices=(0,))]
    )

    [result] = run_needle_benchmark([fixture], BUDGET, [KeepEverythingStrategy()])

    assert result.strategy_name == "KeepEverythingStrategy"
    assert result.needle_retention == 100.0
