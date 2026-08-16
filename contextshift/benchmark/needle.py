"""
Needle-retention evaluation: does a strategy's selection preserve what
a probe actually needs, not just how much of it, in general terms, it kept?
"""
from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from contextshift.benchmark.probes import ConversationFixture, Probe
from contextshift.benchmark.runner import BenchmarkResult
from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextStrategy, total_tokens


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    """
    Whether one probe's load-bearing messages survived one strategy's
    selection, for one fixture.

    Args:
        fixture_name: Which fixture this outcome came from.
        probe: The probe being checked.
        retained_count: How many of `probe.load_bearing_indices` are
            present in the strategy's kept messages.
        total_count: `len(probe.load_bearing_indices)`.
    """

    fixture_name: str
    probe: Probe
    retained_count: int
    total_count: int

    @property
    def satisfied(self) -> bool:
        """True only if every load-bearing message survived -- partial credit doesn't count as an answer."""
        return self.retained_count == self.total_count


def evaluate_fixture(fixture: ConversationFixture, kept: Sequence[Message]) -> list[ProbeOutcome]:
    """
    Check every probe in `fixture` against `kept` -- the messages a
    strategy's `ContextResult.messages` actually returned.

    Matches by object identity (`id()`), not value equality, the same
    discipline `docs/decisions/0004-context-strategy-interface.md`
    already applies to `ContextStrategy.excluded` -- otherwise two
    fixture messages with coincidentally identical text would collide.
    Every strategy in this library preserves the identity of the
    `Message` objects it's given (none of them construct new ones),
    which is what makes this comparison valid.
    """
    kept_ids = {id(m) for m in kept}
    outcomes = []
    for probe in fixture.probes:
        load_bearing = [fixture.messages[i] for i in probe.load_bearing_indices]
        retained = sum(1 for m in load_bearing if id(m) in kept_ids)
        outcomes.append(
            ProbeOutcome(
                fixture_name=fixture.name,
                probe=probe,
                retained_count=retained,
                total_count=len(load_bearing),
            )
        )
    return outcomes


def run_needle_benchmark(
    fixtures: Sequence[ConversationFixture],
    budget: TokenBudget,
    strategies: Sequence[ContextStrategy],
) -> list[BenchmarkResult]:
    """
    Run every strategy against every fixture and report needle
    retention: not "how many messages survived" (a strategy's own
    definition already answers that -- SlidingWindowStrategy(window_size=10)
    keeping 10 messages is not a finding) but "did the messages a real
    question actually depends on survive."

    Aggregates across the whole fixture suite into one BenchmarkResult
    per strategy: token and message counts are summed across all
    fixtures; `needle_retention` is the fraction of load-bearing
    messages retained across every probe in every fixture;
    `probes_satisfied` is an "X / Y" string -- how many probes were
    *fully* satisfied (every load-bearing message survived) out of
    the total number of probes run.

    Same determinism guarantee as `run_benchmark()`: no model call, no
    network, nothing that varies run to run except latency itself.
    Raises if `fixtures` is empty rather than silently reporting 100%
    retention of nothing.
    """
    if not fixtures:
        raise ValueError("run_needle_benchmark requires at least one fixture")

    results: list[BenchmarkResult] = []

    for strategy in strategies:
        total_messages_kept = 0
        total_messages_discarded = 0
        total_tokens_kept = 0
        total_tokens_discarded = 0
        total_latency = 0.0
        needle_retained = 0
        needle_total = 0
        probes_satisfied_count = 0
        probes_total_count = 0

        for fixture in fixtures:
            start = time.perf_counter()
            context_result = strategy.build(fixture.messages, budget)
            total_latency += time.perf_counter() - start

            total_messages_kept += len(context_result.messages)
            total_messages_discarded += len(context_result.excluded)
            total_tokens_kept += total_tokens(context_result.messages)
            total_tokens_discarded += total_tokens(context_result.excluded)

            for outcome in evaluate_fixture(fixture, context_result.messages):
                needle_retained += outcome.retained_count
                needle_total += outcome.total_count
                probes_total_count += 1
                if outcome.satisfied:
                    probes_satisfied_count += 1

        total_tok = total_tokens_kept + total_tokens_discarded
        percentage_retained = 100.0 if total_tok == 0 else (total_tokens_kept / total_tok) * 100
        needle_retention = 100.0 if needle_total == 0 else (needle_retained / needle_total) * 100

        results.append(
            BenchmarkResult(
                strategy_name=type(strategy).__name__,
                messages_kept=total_messages_kept,
                messages_discarded=total_messages_discarded,
                tokens_kept=total_tokens_kept,
                tokens_discarded=total_tokens_discarded,
                percentage_retained=percentage_retained,
                latency_seconds=total_latency,
                needle_retention=needle_retention,
                needle_retained_count=needle_retained,
                needle_total_count=needle_total,
                probes_satisfied=f"{probes_satisfied_count} / {probes_total_count}",
            )
        )

    return results
