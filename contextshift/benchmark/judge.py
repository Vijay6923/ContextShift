"""
Optional, opt-in LLM-scored judging layer.

Needle retention (contextshift.benchmark.needle) asks a deterministic
question: did the load-bearing messages survive selection? It never
calls a model. This module asks the question needle retention is a
proxy *for*: given what a strategy actually selected, does a real
model answer the probe's question correctly?

Opt-in, not a fallback or a richer default, for a specific reason:
calling a model is slow, costs money, and is non-deterministic --
three properties that would break the "runs in CI with no network"
guarantee every other part of this package provides. A caller who
wants this tier asks for it explicitly, by supplying a provider and a
judge to `run_judged_benchmark()`; nothing in this module runs unless
they do, and nothing elsewhere in contextshift.benchmark imports it.

`Judge` is a bring-your-own-implementation Protocol, the same shape as
`LLMProvider`. This module ships exactly one concrete judge,
`SubstringJudge`, which is plain Python string matching -- not an
LLM-as-judge. An LLM-as-judge implementation would need to own a
judging prompt, and owning prompt text is exactly what this project
has never done for any other capability (ADR 0004, ADR 0006, ADR
0007, ADR 0011) -- a caller who wants that is free to write a `Judge`
that wraps an `LLMProvider` themselves.
"""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from contextshift.benchmark.probes import ConversationFixture
from contextshift.core import Message, TokenBudget
from contextshift.llm.base import LLMProvider
from contextshift.strategies.base import ContextStrategy


@runtime_checkable
class Judge(Protocol):
    """
    Anything that can score whether a model's answer matches what a
    probe expected.

    Deliberately separate from LLMProvider: a provider turns messages
    into a reply; a judge turns (an expected answer, an actual answer)
    into a pass/fail. A structural Protocol, per
    docs/decisions/0005-protocol-over-abc.md -- the same pluggability
    story as every other interface in this library.
    """

    def score(self, expected_answer: str, actual_answer: str) -> bool:
        """Return True if actual_answer correctly answers what expected_answer represents."""
        ...


class SubstringJudge:
    """
    A Judge (contextshift.benchmark.judge.Judge) that checks whether
    the expected answer appears in the model's answer, case-insensitive.

    The one concrete judge this module ships. Deliberately not an
    LLM-as-judge -- see this module's docstring for why. Works well
    for fixtures with short, unambiguous expected answers ("Alex",
    "Tuesday") and poorly for fixtures expecting a paraphrase; author
    `expected_answer` with that in mind, or supply your own Judge.
    """

    def score(self, expected_answer: str, actual_answer: str) -> bool:
        return expected_answer.strip().lower() in actual_answer.strip().lower()


@dataclass(frozen=True, slots=True)
class JudgedProbeRun:
    """One (probe, run) outcome: the model's actual answer and whether the judge scored it correct."""

    fixture_name: str
    question: str
    actual_answer: str
    correct: bool


@dataclass(frozen=True, slots=True)
class JudgedResult:
    """
    The outcome of running one strategy's selections through a real
    provider and judge, across every probe in every fixture, repeated
    `runs` times.

    Never a single number: `accuracy_mean` and `accuracy_stdev` are
    reported together because a model's answers are not deterministic
    -- one run's score is a sample, not a measurement.

    Args:
        strategy_name: type(strategy).__name__.
        runs: How many times each probe was actually asked.
        accuracy_mean: Mean percentage of probes answered correctly,
            across `runs` repetitions.
        accuracy_stdev: Standard deviation of that percentage across
            runs. 0.0 when runs == 1 -- nothing to vary.
        raw_runs: Every individual judged answer, for a caller who
            wants to inspect specific failures, not just the aggregate.
    """

    strategy_name: str
    runs: int
    accuracy_mean: float
    accuracy_stdev: float
    raw_runs: tuple[JudgedProbeRun, ...]


def run_judged_benchmark(
    fixtures: Sequence[ConversationFixture],
    budget: TokenBudget,
    strategies: Sequence[ContextStrategy],
    provider: LLMProvider,
    judge: Judge,
    runs: int = 3,
) -> list[JudgedResult]:
    """
    For every strategy: select context for each fixture, ask
    `provider` every probe's question against that selection, and use
    `judge` to score the answer against `probe.expected_answer`.
    Repeated `runs` times per probe; reports mean and standard
    deviation, never a single number, since answers from a real model
    are not deterministic.

    Probes with `expected_answer=None` are skipped -- they exist for
    needle retention only (contextshift.benchmark.needle), not this
    tier, and are not silently scored as wrong.

    Raises if not a single probe across `fixtures` has an
    `expected_answer` set, rather than reporting `accuracy_mean=0.0`
    for every strategy. Zero scoreable probes means nothing was ever
    asked or judged -- reporting 0% would be indistinguishable from
    "asked and got every answer wrong," which is a different, false
    claim. This is why `needle.py`'s and `runner.py`'s "0 out of 0 ==
    100%, nothing to lose" convention is deliberately *not* reused
    here: that convention answers "how much survived," where a vacuous
    "everything" is the right vacuous truth; this function answers
    "how accurate were the answers," where a vacuous number in either
    direction (0% or 100%) misrepresents "no data" as a real result.

    This is the only function in contextshift.benchmark that makes a
    network call. Nothing else in this package does, and this function
    never runs unless a caller explicitly supplies a provider and a
    judge.
    """
    if runs < 1:
        raise ValueError(f"runs must be at least 1, got {runs}")
    if not fixtures:
        raise ValueError("run_judged_benchmark requires at least one fixture")
    if not any(probe.expected_answer is not None for fixture in fixtures for probe in fixture.probes):
        raise ValueError(
            "run_judged_benchmark requires at least one probe with expected_answer set -- "
            "every probe across every fixture has expected_answer=None, so there is nothing "
            "to ask a provider or judge."
        )

    results: list[JudgedResult] = []

    for strategy in strategies:
        # Selection is computed once per (strategy, fixture) pair, not
        # once per run -- context_result never depends on `runs`, only
        # provider.complete()'s answer does. Recomputing it inside the
        # runs loop wasted latency for every strategy and, for one that
        # calls a real model during build() (SummarizationStrategy),
        # meant paying for `runs` redundant summarization calls per
        # fixture for zero added signal.
        context_results = [strategy.build(fixture.messages, budget) for fixture in fixtures]

        run_accuracies: list[float] = []
        all_raw: list[JudgedProbeRun] = []

        for _ in range(runs):
            correct = 0
            total = 0
            for fixture, context_result in zip(fixtures, context_results):
                for probe in fixture.probes:
                    if probe.expected_answer is None:
                        continue
                    prompt = [*context_result.messages, Message(role="user", content=probe.question)]
                    try:
                        actual_answer = provider.complete(prompt)
                    except Exception as e:
                        # A provider failure on one probe (network error,
                        # rate limit exhausted, ...) must not discard every
                        # already-judged, already-paid-for answer collected
                        # so far in this run -- or every completed run for
                        # this strategy, or every completed strategy before
                        # it. Skip this probe (excluded from total/correct,
                        # the same as an expected_answer=None probe -- a
                        # provider outage isn't evidence the strategy
                        # answered incorrectly) and keep going.
                        print(
                            f"[JUDGE ERROR] provider.complete() failed for "
                            f"fixture={fixture.name!r} question={probe.question!r}: {e}"
                        )
                        continue
                    total += 1
                    is_correct = judge.score(probe.expected_answer, actual_answer)
                    if is_correct:
                        correct += 1
                    all_raw.append(
                        JudgedProbeRun(
                            fixture_name=fixture.name,
                            question=probe.question,
                            actual_answer=actual_answer,
                            correct=is_correct,
                        )
                    )
            run_accuracies.append(0.0 if total == 0 else (correct / total) * 100)

        results.append(
            JudgedResult(
                strategy_name=type(strategy).__name__,
                runs=runs,
                accuracy_mean=statistics.mean(run_accuracies),
                accuracy_stdev=statistics.stdev(run_accuracies) if runs > 1 else 0.0,
                raw_runs=tuple(all_raw),
            )
        )

    return results


def judged_to_markdown(results: Sequence[JudgedResult]) -> str:
    """Render judged results as a Markdown table. Same plain-string-formatting approach as runner.to_markdown()."""
    headers = ("Strategy", "Runs", "Accuracy Mean", "Accuracy Stdev")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.strategy_name,
                    str(result.runs),
                    f"{result.accuracy_mean:.2f}%",
                    f"{result.accuracy_stdev:.2f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines)
