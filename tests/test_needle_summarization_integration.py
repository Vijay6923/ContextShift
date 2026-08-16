"""
Integration tests: SummarizationStrategy running end-to-end through
both of contextshift.benchmark's tiers.

The deterministic tier (run_needle_benchmark, backed by FakeSummarizer)
proves the actual claim made in SummarizationStrategy's docstring and
docs/decisions/0015-summarization-strategy.md: the first ContextStrategy
that depends on a real model call can still run in CI with no network
access.

The judged tier (run_judged_benchmark) is the *other* half of that same
ADR's addendum: needle retention's identity-based matching cannot give
SummarizationStrategy a meaningful score with a real Summarizer, because
a summary that genuinely preserves a fact does so by paraphrasing it
into new text, not by keeping the original Message object alive. The
test below proves SummarizationStrategy runs cleanly through the judged
tier's plumbing -- selection, prompt construction, scoring, aggregation
-- with fakes standing in for both the summarizer and the answering
model, since neither is meant to be real in a network-free test suite.
It is a wiring test, not a quality measurement: with a real Summarizer
and a real LLMProvider (not exercised here), this is the tier that
actually answers "does SummarizationStrategy work," per the ADR 0015
addendum.
"""
from pathlib import Path

from contextshift.benchmark.judge import SubstringJudge, run_judged_benchmark
from contextshift.benchmark.needle import run_needle_benchmark
from contextshift.benchmark.probes import load_fixtures
from contextshift.core import TokenBudget
from contextshift.strategies import RecencyStrategy, SummarizationStrategy
from contextshift.testing import FakeLLMProvider, FakeSummarizer
from contextshift.tokenizers.heuristic import HeuristicTokenizer

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "conversations"


def test_summarization_strategy_runs_cleanly_through_the_deterministic_needle_benchmark():
    fixtures = load_fixtures(FIXTURES_DIR)
    budget = TokenBudget(max_tokens=350, safety_margin=50)
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=6)

    [result] = run_needle_benchmark(fixtures, budget, [strategy])

    assert result.strategy_name == "SummarizationStrategy"
    assert result.needle_retention is not None
    assert 0.0 <= result.needle_retention <= 100.0
    assert result.probes_satisfied is not None
    # No network call happened -- FakeSummarizer would raise or hang
    # if it ever tried one, and this assertion running at all is proof
    # the whole benchmark completed without one.


def test_summarization_strategy_is_repeatable_given_a_fake_summarizer():
    # "Not deterministic unless the Summarizer it's given is" -- proven
    # by running twice and getting byte-identical results, the property
    # a real Summarizer (backed by a real model) could not offer.
    fixtures = load_fixtures(FIXTURES_DIR)
    budget = TokenBudget(max_tokens=350, safety_margin=50)

    def build_strategy():
        return SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=6)

    [first] = run_needle_benchmark(fixtures, budget, [build_strategy()])
    [second] = run_needle_benchmark(fixtures, budget, [build_strategy()])

    assert first.needle_retention == second.needle_retention
    assert first.probes_satisfied == second.probes_satisfied
    assert first.tokens_kept == second.tokens_kept


def test_summarization_strategy_can_be_compared_against_other_strategies_in_one_run():
    fixtures = load_fixtures(FIXTURES_DIR)
    budget = TokenBudget(max_tokens=350, safety_margin=50)

    results = run_needle_benchmark(
        fixtures,
        budget,
        [RecencyStrategy(), SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=6)],
    )

    assert {r.strategy_name for r in results} == {"RecencyStrategy", "SummarizationStrategy"}


def test_summarization_strategy_runs_cleanly_through_the_judged_benchmark():
    # A small subset -- run_judged_benchmark calls a provider once per
    # probe per run; the full 55-probe suite would just make this test
    # slow for no additional coverage, since the point is the wiring,
    # not the fixture count.
    fixtures = load_fixtures(FIXTURES_DIR)[:3]
    budget = TokenBudget(max_tokens=350, safety_margin=50)
    strategy = SummarizationStrategy(FakeSummarizer(), HeuristicTokenizer(), keep_recent=6)

    [result] = run_judged_benchmark(
        fixtures,
        budget,
        [strategy],
        provider=FakeLLMProvider(complete_response="a fake answer"),
        judge=SubstringJudge(),
        runs=1,
    )

    assert result.strategy_name == "SummarizationStrategy"
    assert result.runs == 1
    assert 0.0 <= result.accuracy_mean <= 100.0
    assert len(result.raw_runs) > 0
    # No network call happened -- FakeSummarizer and FakeLLMProvider
    # would both raise or hang if either ever attempted one.
