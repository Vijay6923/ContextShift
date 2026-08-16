"""
Tests for contextshift.benchmark.judge: the opt-in, LLM-scored tier.

Uses FakeLLMProvider throughout -- no network access, no API key --
even though run_judged_benchmark() itself is designed for real
providers. That's exactly what makes it testable: the function takes
any LLMProvider, and a fake satisfies the protocol the same way it
does everywhere else in this project.
"""
import pytest

from contextshift.benchmark.judge import (
    Judge,
    SubstringJudge,
    judged_to_markdown,
    run_judged_benchmark,
)
from contextshift.benchmark.probes import ConversationFixture, Probe
from contextshift.core import Message, TokenBudget
from contextshift.strategies import RecencyStrategy
from contextshift.testing import FakeLLMProvider

BUDGET = TokenBudget(max_tokens=4000, safety_margin=200)


def _msg(role, content, token_count=10):
    return Message(role=role, content=content, token_count=token_count)


def _fixture(name, messages, probes):
    return ConversationFixture(
        name=name, failure_mode="test", description="d", messages=tuple(messages), probes=tuple(probes)
    )


# -- SubstringJudge -------------------------------------------------------


def test_substring_judge_matches_case_insensitively():
    judge = SubstringJudge()
    assert judge.score("Paris", "I think the answer is paris.") is True


def test_substring_judge_rejects_when_absent():
    judge = SubstringJudge()
    assert judge.score("Paris", "I think the answer is London.") is False


def test_substring_judge_satisfies_judge_protocol():
    assert isinstance(SubstringJudge(), Judge)


def test_something_lacking_score_does_not_satisfy_judge_protocol():
    class NotAJudge:
        pass

    assert not isinstance(NotAJudge(), Judge)


# -- run_judged_benchmark --------------------------------------------------


def test_run_judged_benchmark_requires_at_least_one_run():
    fixture = _fixture("f", [_msg("user", "a")], [])
    with pytest.raises(ValueError, match="runs must be at least 1"):
        run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], FakeLLMProvider(), SubstringJudge(), runs=0)


def test_run_judged_benchmark_requires_at_least_one_fixture():
    with pytest.raises(ValueError, match="at least one fixture"):
        run_judged_benchmark([], BUDGET, [RecencyStrategy()], FakeLLMProvider(), SubstringJudge())


def test_run_judged_benchmark_scores_correct_answers():
    fixture = _fixture(
        "f",
        [_msg("user", "What's the capital of France?")],
        [Probe(question="What's the capital?", load_bearing_indices=(0,), expected_answer="Paris")],
    )
    provider = FakeLLMProvider(complete_response="The capital is Paris.")

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    assert result.strategy_name == "RecencyStrategy"
    assert result.runs == 1
    assert result.accuracy_mean == 100.0
    assert result.accuracy_stdev == 0.0
    assert len(result.raw_runs) == 1
    assert result.raw_runs[0].correct is True
    assert result.raw_runs[0].actual_answer == "The capital is Paris."


def test_run_judged_benchmark_scores_incorrect_answers():
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer="Paris")],
    )
    provider = FakeLLMProvider(complete_response="I don't know.")

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    assert result.accuracy_mean == 0.0
    assert result.raw_runs[0].correct is False


def test_run_judged_benchmark_skips_probes_without_expected_answer():
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer=None)],
    )
    provider = FakeLLMProvider(complete_response="anything")

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    # No scoreable probes -- nothing asked, nothing to be right or wrong about.
    assert result.raw_runs == ()


def test_run_judged_benchmark_repeats_runs_and_reports_stdev_of_zero_for_a_deterministic_fake():
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer="Paris")],
    )
    provider = FakeLLMProvider(complete_response="Paris")

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=3)

    assert result.runs == 3
    assert len(result.raw_runs) == 3
    assert result.accuracy_mean == 100.0
    assert result.accuracy_stdev == 0.0  # FakeLLMProvider is deterministic, so every run agrees


def test_run_judged_benchmark_sends_the_probe_question_after_the_selected_context():
    fixture = _fixture(
        "f",
        [_msg("user", "earlier turn")],
        [Probe(question="What did I just say?", load_bearing_indices=(0,), expected_answer="earlier turn")],
    )
    provider = FakeLLMProvider(complete_response="earlier turn")

    run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    sent_messages, _ = provider.complete_calls[0]
    assert [m.content for m in sent_messages] == ["earlier turn", "What did I just say?"]


def test_judged_to_markdown_produces_a_table():
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer="Paris")],
    )
    results = run_judged_benchmark(
        [fixture], BUDGET, [RecencyStrategy()], FakeLLMProvider(complete_response="Paris"), SubstringJudge()
    )

    markdown = judged_to_markdown(results)
    lines = markdown.splitlines()

    assert lines[0].startswith("| Strategy |")
    assert "RecencyStrategy" in lines[2]
