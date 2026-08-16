"""
Tests against the real, committed fixture suite in
tests/fixtures/conversations/ -- distinct from test_benchmark_needle.py,
which tests contextshift.benchmark.needle's logic against small,
synthetic fixtures constructed inline.

These tests exist so the committed fixture set itself can't silently
rot: every fixture must still load, every probe index must still be
valid, and the suite must still cover every failure mode named in
tests/fixtures/conversations/README.md.
"""
from pathlib import Path

from contextshift.benchmark.needle import run_needle_benchmark
from contextshift.benchmark.probes import load_fixtures
from contextshift.core import TokenBudget
from contextshift.strategies import PinnedRecencyStrategy, RecencyStrategy, SlidingWindowStrategy

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "conversations"

EXPECTED_FAILURE_MODES = {
    "early-establishment",
    "topic-drift",
    "interleaved-threads",
    "correction-of-earlier-answer",
    "long-tool-output",
    "pinned-instruction-under-pressure",
}


def test_at_least_forty_fixtures_exist():
    # Started at 10; expanded per-failure-mode coverage in a follow-up
    # pass (each original 10 fixture stayed byte-identical -- see
    # tests/fixtures/conversations/_generate.py's "Expansion" section).
    fixtures = load_fixtures(FIXTURES_DIR)
    assert len(fixtures) >= 40


def test_every_named_failure_mode_has_at_least_one_fixture():
    fixtures = load_fixtures(FIXTURES_DIR)
    covered = {f.failure_mode for f in fixtures}
    missing = EXPECTED_FAILURE_MODES - covered
    assert not missing, f"no fixture covers: {missing}"


def test_every_fixture_has_at_least_one_probe():
    fixtures = load_fixtures(FIXTURES_DIR)
    for fixture in fixtures:
        assert len(fixture.probes) >= 1, f"{fixture.name} has no probes"


def test_every_probe_has_at_least_one_load_bearing_message():
    fixtures = load_fixtures(FIXTURES_DIR)
    for fixture in fixtures:
        for probe in fixture.probes:
            assert len(probe.load_bearing_indices) >= 1, (
                f"{fixture.name}: {probe.question!r} has no load-bearing messages"
            )


def test_pinned_instruction_fixture_actually_has_a_pinned_message():
    fixtures = {f.name: f for f in load_fixtures(FIXTURES_DIR)}
    fixture = fixtures["pinned-instruction-under-pressure"]
    assert any(m.is_pinned for m in fixture.messages)


def test_needle_benchmark_runs_cleanly_over_the_full_suite():
    # The real, end-to-end smoke test: every fixture, every shipped
    # strategy, one deterministic run, no exceptions, sane output shape.
    fixtures = load_fixtures(FIXTURES_DIR)
    budget = TokenBudget(max_tokens=350, safety_margin=50)

    results = run_needle_benchmark(
        fixtures,
        budget,
        [RecencyStrategy(), SlidingWindowStrategy(window_size=10), PinnedRecencyStrategy(recent_buffer=6)],
    )

    assert len(results) == 3
    for result in results:
        assert result.needle_retention is not None
        assert 0.0 <= result.needle_retention <= 100.0
        assert result.probes_satisfied is not None


def test_needle_retention_differs_across_strategies_on_the_real_suite():
    # The whole point of this benchmark: it must be possible for
    # strategies to actually differ on this metric, not just on token
    # counts. If every strategy scored identically here, the fixture
    # suite would not be doing its job.
    fixtures = load_fixtures(FIXTURES_DIR)
    budget = TokenBudget(max_tokens=350, safety_margin=50)

    results = run_needle_benchmark(
        fixtures,
        budget,
        [RecencyStrategy(), SlidingWindowStrategy(window_size=10), PinnedRecencyStrategy(recent_buffer=6)],
    )

    retentions = {r.strategy_name: r.needle_retention for r in results}
    assert len(set(retentions.values())) > 1, f"all strategies scored identically: {retentions}"


def test_pinned_recency_beats_the_others_on_the_pinned_instruction_fixture():
    # A specific, checkable claim: on the one fixture designed to test
    # pinning, the strategy that supports pinning should retain the
    # needle and the two that don't should not -- not just "different
    # numbers," but the *correct* direction.
    fixtures = {f.name: f for f in load_fixtures(FIXTURES_DIR)}
    fixture = fixtures["pinned-instruction-under-pressure"]
    budget = TokenBudget(max_tokens=350, safety_margin=50)

    [pinned_result] = run_needle_benchmark([fixture], budget, [PinnedRecencyStrategy(recent_buffer=6)])
    [recency_result] = run_needle_benchmark([fixture], budget, [RecencyStrategy()])
    [window_result] = run_needle_benchmark([fixture], budget, [SlidingWindowStrategy(window_size=10)])

    assert pinned_result.needle_retention == 100.0
    assert recency_result.needle_retention == 0.0
    assert window_result.needle_retention == 0.0
