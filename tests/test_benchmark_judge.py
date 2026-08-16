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


def test_run_judged_benchmark_skips_individual_probes_without_expected_answer():
    # A *mix* of scoreable and needle-only probes -- the None one must
    # be skipped (not counted, not sent to the provider) while the real
    # one is still judged normally.
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [
            Probe(question="needle-only", load_bearing_indices=(0,), expected_answer=None),
            Probe(question="q", load_bearing_indices=(0,), expected_answer="hi"),
        ],
    )
    provider = FakeLLMProvider(complete_response="hi")

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    assert len(result.raw_runs) == 1
    assert result.raw_runs[0].question == "q"
    assert result.accuracy_mean == 100.0


def test_run_judged_benchmark_raises_when_no_probe_anywhere_has_an_expected_answer():
    # If every probe across every fixture is needle-only, there is
    # nothing to ask a provider or judge -- this must not silently
    # report accuracy_mean=0.0 (indistinguishable from "asked and got
    # every answer wrong"). See the docstring on run_judged_benchmark
    # for why this diverges from needle.py's "0 out of 0 == 100%"
    # convention rather than reusing it.
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer=None)],
    )
    provider = FakeLLMProvider(complete_response="anything")

    with pytest.raises(ValueError, match="expected_answer"):
        run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)


def test_run_judged_benchmark_calls_build_once_per_fixture_regardless_of_runs():
    # Regression test: context_result used to be recomputed inside the
    # `for _ in range(runs)` loop, so a strategy's build() ran `runs`
    # times per fixture even though only provider.complete() is meant
    # to vary across runs. For a strategy whose build() makes a real,
    # billed model call (SummarizationStrategy), that meant paying for
    # `runs` redundant summarizations for zero added signal.
    build_call_count = 0

    class _CountingStrategy:
        def build(self, messages, budget):
            nonlocal build_call_count
            build_call_count += 1
            return RecencyStrategy().build(messages, budget)

    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [Probe(question="q", load_bearing_indices=(0,), expected_answer="hi")],
    )
    provider = FakeLLMProvider(complete_response="hi")

    run_judged_benchmark([fixture], BUDGET, [_CountingStrategy()], provider, SubstringJudge(), runs=5)

    assert build_call_count == 1  # once, not once per run


def test_run_judged_benchmark_survives_a_provider_failure_on_one_probe():
    # Regression test: provider.complete() used to be called with no
    # exception handling, so one failing probe (out of many) discarded
    # every already-judged answer collected so far -- for a real
    # provider (real, billed API calls), that meant losing all prior
    # spend on one late transient failure. A failing probe must now be
    # skipped, not fatal to the whole run.
    fixture = _fixture(
        "f",
        [_msg("user", "hi")],
        [
            Probe(question="q1", load_bearing_indices=(0,), expected_answer="hi"),
            Probe(question="q2", load_bearing_indices=(0,), expected_answer="hi"),
            Probe(question="q3", load_bearing_indices=(0,), expected_answer="hi"),
        ],
    )

    class _FlakyProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, max_tokens=1024):
            self.calls += 1
            if self.calls == 2:  # fail exactly once, on the second call
                raise ConnectionError("simulated transient network failure")
            return "hi"

        def stream(self, messages, max_tokens=1024):
            raise NotImplementedError

    provider = _FlakyProvider()

    [result] = run_judged_benchmark([fixture], BUDGET, [RecencyStrategy()], provider, SubstringJudge(), runs=1)

    # 3 probes attempted, 1 failed and was skipped -> 2 judged, both correct.
    assert provider.calls == 3
    assert len(result.raw_runs) == 2
    assert result.accuracy_mean == 100.0
    assert all(run.correct for run in result.raw_runs)


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
