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
    (messages, budget) input -- or, for `run_needle_benchmark()`,
    aggregated across an entire fixture suite.

    `percentage_retained` is token-weighted, not message-count-weighted
    -- `tokens_kept / (tokens_kept + tokens_discarded) * 100` -- since
    token count, not message count, is what a budget actually limits. A
    conversation with no input tokens at all (e.g. an empty message
    list) is defined as 100% retained: there was nothing to lose.

    `needle_retention` and `probes_satisfied` answer a different
    question than everything else on this type: not "how much did the
    strategy keep" (which a strategy's own definition already implies
    -- SlidingWindowStrategy(window_size=10) keeping 10 messages is not
    a finding) but "did it keep the messages a real question actually
    needed." Both are `None` for a plain `run_benchmark()` call, which
    has no probes to check against; both are populated by
    `contextshift.benchmark.needle.run_needle_benchmark()`. See
    docs/decisions/0013-needle-retention-benchmark.md for why this
    distinction is the point of the needle-retention benchmark existing
    at all.

    Args:
        strategy_name: `type(strategy).__name__`, e.g.
            "PinnedRecencyStrategy". Two instances of the *same* class
            benchmarked with different constructor arguments will
            share a label -- not distinguished here, since nothing
            using this module today benchmarks two configurations of
            one strategy class at once.
        messages_kept: len(result.messages), summed across fixtures
            for a needle-retention run.
        messages_discarded: len(result.excluded), summed likewise.
        tokens_kept: total_tokens(result.messages), summed likewise.
        tokens_discarded: total_tokens(result.excluded), summed likewise.
        percentage_retained: See above.
        latency_seconds: Wall-clock time for the `build()` call(s),
            measured with `time.perf_counter()` -- summed across
            fixtures for a needle-retention run.
        needle_retention: Percentage of load-bearing messages (across
            every probe in every fixture) that survived selection.
            `None` when no probes were run. A bare percentage invites
            exactly the wrong reading -- "45%" reads as "nearly half,"
            not "5 out of 11" -- which is why `to_markdown()`/`to_csv()`
            render this alongside `needle_retained_count` /
            `needle_total_count`, not as a percentage alone.
        needle_retained_count: How many load-bearing messages survived,
            summed across every probe in every fixture. `None` when no
            probes were run. `needle_retention ==
            needle_retained_count / needle_total_count * 100`.
        needle_total_count: Total load-bearing messages checked, summed
            across every probe in every fixture. `None` when no probes
            were run.
        probes_satisfied: `"X / Y"` -- how many probes had *every*
            load-bearing message survive, out of how many probes ran.
            `None` when no probes were run. A probe with more than one
            load-bearing message can fail this (partial credit doesn't
            count) while still contributing partial credit to
            `needle_retention` -- the two metrics answer related but
            distinct questions, not the same one twice.
    """

    strategy_name: str
    messages_kept: int
    messages_discarded: int
    tokens_kept: int
    tokens_discarded: int
    percentage_retained: float
    latency_seconds: float
    needle_retention: float | None = None
    needle_retained_count: int | None = None
    needle_total_count: int | None = None
    probes_satisfied: str | None = None


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
_NEEDLE_CSV_FIELDS = ("needle_retention", "needle_retained_count", "needle_total_count", "probes_satisfied")


def _has_needle_data(results: Sequence[BenchmarkResult]) -> bool:
    return any(r.needle_retention is not None for r in results)


def _format_needle_retention(result: BenchmarkResult) -> str:
    """
    "14 / 55 (25.45%)" when raw counts are available, "25.45%" alone
    otherwise (e.g. a BenchmarkResult constructed directly rather than
    via run_needle_benchmark()) -- a bare percentage reads as "roughly
    a quarter," not "14 out of 55," and the raw counts are what make a
    reader stop and ask whether 55 probes is even a large enough
    sample, the way a percentage alone lets a reader skip that question.
    """
    if result.needle_retention is None:
        return "--"
    if result.needle_retained_count is None or result.needle_total_count is None:
        return f"{result.needle_retention:.2f}%"
    return f"{result.needle_retained_count} / {result.needle_total_count} ({result.needle_retention:.2f}%)"


def to_csv(results: Sequence[BenchmarkResult]) -> str:
    """
    Render `results` as CSV text (header row plus one row per result,
    in the given order). Uses the standard library `csv` module only --
    no new dependency. Returns a string; writing it to a file or stdout
    is a caller decision, not this function's.

    The `needle_retention` / `probes_satisfied` columns are included
    only when at least one result actually has them (i.e. came from
    `run_needle_benchmark()`) -- a plain `run_benchmark()` call keeps
    the exact same CSV shape it always has.
    """
    include_needle = _has_needle_data(results)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_FIELDS + (_NEEDLE_CSV_FIELDS if include_needle else ()))
    for result in results:
        row = [
            result.strategy_name,
            result.messages_kept,
            result.messages_discarded,
            result.tokens_kept,
            result.tokens_discarded,
            f"{result.percentage_retained:.2f}",
            f"{result.latency_seconds:.6f}",
        ]
        if include_needle:
            row.append("" if result.needle_retention is None else f"{result.needle_retention:.2f}")
            row.append("" if result.needle_retained_count is None else str(result.needle_retained_count))
            row.append("" if result.needle_total_count is None else str(result.needle_total_count))
            row.append(result.probes_satisfied or "")
        writer.writerow(row)
    return buffer.getvalue()


def to_markdown(results: Sequence[BenchmarkResult]) -> str:
    """
    Render `results` as a Markdown table, in the given order. Plain
    string formatting only -- no templating library. Returns a string;
    printing or writing it to a file is a caller decision, not this
    function's.

    Same conditional shape as `to_csv()`: needle-retention columns
    appear only when the results actually carry that data.
    """
    include_needle = _has_needle_data(results)
    headers = [
        "Strategy",
        "Kept",
        "Discarded",
        "Tokens Kept",
        "Tokens Discarded",
        "% Retained",
        "Latency (s)",
    ]
    if include_needle:
        headers += ["Needle Retention", "Probes Satisfied"]

    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    for result in results:
        row = [
            result.strategy_name,
            str(result.messages_kept),
            str(result.messages_discarded),
            str(result.tokens_kept),
            str(result.tokens_discarded),
            f"{result.percentage_retained:.2f}%",
            f"{result.latency_seconds:.6f}",
        ]
        if include_needle:
            row.append(_format_needle_retention(result))
            row.append(result.probes_satisfied or "--")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
