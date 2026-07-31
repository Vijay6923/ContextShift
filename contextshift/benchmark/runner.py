"""Deterministic, in-memory benchmarking of ContextStrategy implementations."""
from __future__ import annotations

import csv
import io
import time
from collections.abc import Sequence
from dataclasses import dataclass

from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextStrategy, total_tokens


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """
    The outcome of running one ContextStrategy against one
    (messages, budget) input.

    `percentage_retained` is token-weighted, not message-count-weighted
    -- `tokens_kept / (tokens_kept + tokens_discarded) * 100` -- since
    token count, not message count, is what a budget actually limits. A
    conversation with no input tokens at all (e.g. an empty message
    list) is defined as 100% retained: there was nothing to lose.

    Args:
        strategy_name: `type(strategy).__name__`, e.g.
            "PinnedRecencyStrategy". Two instances of the *same* class
            benchmarked with different constructor arguments will
            share a label -- not distinguished here, since nothing
            using this module today benchmarks two configurations of
            one strategy class at once.
        messages_kept: len(result.messages).
        messages_discarded: len(result.excluded).
        tokens_kept: total_tokens(result.messages).
        tokens_discarded: total_tokens(result.excluded).
        percentage_retained: See above.
        latency_seconds: Wall-clock time for the single `build()` call,
            measured with `time.perf_counter()`.
    """

    strategy_name: str
    messages_kept: int
    messages_discarded: int
    tokens_kept: int
    tokens_discarded: int
    percentage_retained: float
    latency_seconds: float


def run_benchmark(
    messages: Sequence[Message],
    budget: TokenBudget,
    strategies: Sequence[ContextStrategy],
) -> list[BenchmarkResult]:
    """
    Run every strategy in `strategies` against the identical
    `(messages, budget)` input and return one BenchmarkResult per
    strategy, in the same order `strategies` was given.

    Never calls an LLM, a network, or anything non-deterministic --
    every metric is derived from what ContextStrategy.build() already
    returns (contextshift.strategies.base.ContextResult) plus
    total_tokens(), the same helper every strategy already depends on.
    `messages` is not mutated; each strategy receives it directly
    (ContextStrategy.build() is already required not to mutate its
    input, per docs/decisions/0004-context-strategy-interface.md).
    """
    results: list[BenchmarkResult] = []

    for strategy in strategies:
        start = time.perf_counter()
        context_result = strategy.build(messages, budget)
        latency_seconds = time.perf_counter() - start

        tokens_kept = total_tokens(context_result.messages)
        tokens_discarded = total_tokens(context_result.excluded)
        total = tokens_kept + tokens_discarded
        percentage_retained = 100.0 if total == 0 else (tokens_kept / total) * 100

        results.append(
            BenchmarkResult(
                strategy_name=type(strategy).__name__,
                messages_kept=len(context_result.messages),
                messages_discarded=len(context_result.excluded),
                tokens_kept=tokens_kept,
                tokens_discarded=tokens_discarded,
                percentage_retained=percentage_retained,
                latency_seconds=latency_seconds,
            )
        )

    return results


_CSV_FIELDS = (
    "strategy_name",
    "messages_kept",
    "messages_discarded",
    "tokens_kept",
    "tokens_discarded",
    "percentage_retained",
    "latency_seconds",
)


def to_csv(results: Sequence[BenchmarkResult]) -> str:
    """
    Render `results` as CSV text (header row plus one row per result,
    in the given order). Uses the standard library `csv` module only --
    no new dependency. Returns a string; writing it to a file or stdout
    is a caller decision, not this function's.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_FIELDS)
    for result in results:
        writer.writerow(
            [
                result.strategy_name,
                result.messages_kept,
                result.messages_discarded,
                result.tokens_kept,
                result.tokens_discarded,
                f"{result.percentage_retained:.2f}",
                f"{result.latency_seconds:.6f}",
            ]
        )
    return buffer.getvalue()


def to_markdown(results: Sequence[BenchmarkResult]) -> str:
    """
    Render `results` as a Markdown table, in the given order. Plain
    string formatting only -- no templating library. Returns a string;
    printing or writing it to a file is a caller decision, not this
    function's.
    """
    headers = (
        "Strategy",
        "Kept",
        "Discarded",
        "Tokens Kept",
        "Tokens Discarded",
        "% Retained",
        "Latency (s)",
    )
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
                    str(result.messages_kept),
                    str(result.messages_discarded),
                    str(result.tokens_kept),
                    str(result.tokens_discarded),
                    f"{result.percentage_retained:.2f}%",
                    f"{result.latency_seconds:.6f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines)
