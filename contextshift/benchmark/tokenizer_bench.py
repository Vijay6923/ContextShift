"""
Benchmarking Tokenizer implementations against each other.

Same harness idea as the strategy benchmark (contextshift.benchmark.runner),
applied to a different axis: instead of "did a strategy keep the right
messages," this asks "how far off is a tokenizer's estimate from a
reference count." `HeuristicTokenizer`'s error rate has always been
real; this module exists to publish it, rather than leave it implied
by the word "heuristic" in its name.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contextshift.tokenizers.base import Tokenizer


@dataclass(frozen=True, slots=True)
class TokenizerBenchmarkResult:
    """
    How one tokenizer's estimates compare to a reference tokenizer's
    counts, across a corpus of text samples.

    Args:
        tokenizer_name: type(tokenizer).__name__.
        mean_absolute_error: Average |estimate - reference|, in raw
            token count, across the corpus.
        mean_absolute_percentage_error: Average |estimate - reference| / reference,
            as a percentage -- more comparable across texts of very
            different lengths than raw token counts are.
        max_absolute_percentage_error: The single worst-case percentage
            error in the corpus -- knowing how bad the worst case gets
            matters as much as the average, for a budget-sizing
            decision that has to hold even in an unlucky case.
        sample_count: How many text samples were compared.
    """

    tokenizer_name: str
    mean_absolute_error: float
    mean_absolute_percentage_error: float
    max_absolute_percentage_error: float
    sample_count: int


def benchmark_tokenizers(
    corpus: Sequence[str],
    reference: Tokenizer,
    tokenizers: Sequence[Tokenizer],
) -> list[TokenizerBenchmarkResult]:
    """
    Compare every tokenizer in `tokenizers` against `reference`'s
    counts, over `corpus`, in the given order.

    `reference` is not assumed correct in any absolute sense -- it's
    whatever the caller considers ground truth for their use case
    (typically `TiktokenTokenizer`, or a specific model's own counting
    endpoint). A tokenizer equal to `reference` itself is scored the
    same way as any other -- it will simply report zero error, which
    is itself a useful sanity check that the harness works.

    Raises on an empty corpus rather than reporting a meaningless zero
    error over nothing.
    """
    if not corpus:
        raise ValueError("benchmark_tokenizers requires a non-empty corpus")

    reference_counts = [reference.estimate_tokens(text) for text in corpus]

    results: list[TokenizerBenchmarkResult] = []
    for tokenizer in tokenizers:
        absolute_errors: list[int] = []
        percentage_errors: list[float] = []

        for text, ref_count in zip(corpus, reference_counts):
            estimate = tokenizer.estimate_tokens(text)
            error = abs(estimate - ref_count)
            absolute_errors.append(error)
            percentage_errors.append(0.0 if ref_count == 0 else (error / ref_count) * 100)

        results.append(
            TokenizerBenchmarkResult(
                tokenizer_name=type(tokenizer).__name__,
                mean_absolute_error=sum(absolute_errors) / len(absolute_errors),
                mean_absolute_percentage_error=sum(percentage_errors) / len(percentage_errors),
                max_absolute_percentage_error=max(percentage_errors),
                sample_count=len(corpus),
            )
        )

    return results


def tokenizer_benchmark_to_markdown(results: Sequence[TokenizerBenchmarkResult]) -> str:
    """Render tokenizer benchmark results as a Markdown table.

    Same plain-formatting approach as runner.to_markdown().
    """
    headers = ("Tokenizer", "Mean Abs. Error", "Mean % Error", "Max % Error", "Samples")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.tokenizer_name,
                    f"{result.mean_absolute_error:.2f}",
                    f"{result.mean_absolute_percentage_error:.2f}%",
                    f"{result.max_absolute_percentage_error:.2f}%",
                    str(result.sample_count),
                ]
            )
            + " |"
        )
    return "\n".join(lines)
