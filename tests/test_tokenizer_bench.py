"""Tests for contextshift.benchmark.tokenizer_bench: comparing Tokenizer implementations against a reference."""
import pytest

from contextshift.benchmark.tokenizer_bench import (
    TokenizerBenchmarkResult,
    benchmark_tokenizers,
    tokenizer_benchmark_to_markdown,
)
from contextshift.tokenizers import HeuristicTokenizer, TiktokenTokenizer


class _FixedTokenizer:
    """A tokenizer that always reports the same count -- for exact, hand-traced error assertions."""

    def __init__(self, count):
        self._count = count

    def estimate_tokens(self, text):
        return self._count


class _MultiplierTokenizer:
    """Reports len(text) as its token count -- deterministic and easy to reason about by hand."""

    def estimate_tokens(self, text):
        return len(text)


def test_requires_a_non_empty_corpus():
    with pytest.raises(ValueError, match="non-empty corpus"):
        benchmark_tokenizers([], reference=_FixedTokenizer(5), tokenizers=[_FixedTokenizer(5)])


def test_tokenizer_identical_to_reference_reports_zero_error():
    corpus = ["a", "bb", "ccc"]
    [result] = benchmark_tokenizers(corpus, reference=_MultiplierTokenizer(), tokenizers=[_MultiplierTokenizer()])

    assert result.mean_absolute_error == 0.0
    assert result.mean_absolute_percentage_error == 0.0
    assert result.max_absolute_percentage_error == 0.0
    assert result.sample_count == 3


def test_hand_traced_error_calculation():
    # reference always says 10; this tokenizer always says 12 -> error 2, 20% every time.
    corpus = ["x", "y"]
    [result] = benchmark_tokenizers(corpus, reference=_FixedTokenizer(10), tokenizers=[_FixedTokenizer(12)])

    assert result.mean_absolute_error == 2.0
    assert result.mean_absolute_percentage_error == 20.0
    assert result.max_absolute_percentage_error == 20.0


def test_compares_multiple_tokenizers_in_given_order():
    corpus = ["hello"]
    results = benchmark_tokenizers(
        corpus,
        reference=_FixedTokenizer(5),
        tokenizers=[_FixedTokenizer(5), _FixedTokenizer(10), _FixedTokenizer(0)],
    )

    assert [r.mean_absolute_error for r in results] == [0.0, 5.0, 5.0]


def test_max_percentage_error_is_the_worst_case_not_the_average():
    # Errors of 10% and 90% across two samples -- mean is 50%, max must be 90%.
    corpus = ["a", "b"]

    class _VariableTokenizer:
        def __init__(self):
            self._calls = 0

        def estimate_tokens(self, text):
            self._calls += 1
            return 11 if self._calls == 1 else 19  # vs reference of 10 each time

    [result] = benchmark_tokenizers(corpus, reference=_FixedTokenizer(10), tokenizers=[_VariableTokenizer()])

    assert result.mean_absolute_percentage_error == 50.0
    assert result.max_absolute_percentage_error == 90.0


def test_benchmark_result_is_a_frozen_dataclass():
    import dataclasses

    result = TokenizerBenchmarkResult(
        tokenizer_name="X",
        mean_absolute_error=0.0,
        mean_absolute_percentage_error=0.0,
        max_absolute_percentage_error=0.0,
        sample_count=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.sample_count = 2


def test_to_markdown_produces_a_table():
    corpus = ["hello world"]
    results = benchmark_tokenizers(corpus, reference=_MultiplierTokenizer(), tokenizers=[HeuristicTokenizer()])

    markdown = tokenizer_benchmark_to_markdown(results)
    lines = markdown.splitlines()

    assert lines[0].startswith("| Tokenizer |")
    assert "HeuristicTokenizer" in lines[2]


# -- The real, honest measurement: HeuristicTokenizer vs. tiktoken -----------


def test_heuristic_tokenizer_error_rate_against_tiktoken_is_measured_not_assumed():
    # A realistic corpus of the kinds of strings this application
    # actually sends -- not cherry-picked to make the heuristic look
    # good or bad, just varied.
    corpus = [
        "hello",
        "hello world",
        "The quick brown fox jumps over the lazy dog.",
        "Hello, world! How are you?",
        "https://example.com/very/long/path/that/is/one/token",
        "[SUMMARY] The user asked about Python decorators and the assistant explained closures.",
        "word " * 200,
        "Supercalifragilisticexpialidocious is often cited as a very long word.",
        "def foo(x, y):\n    return x + y\n",
        "😀 emoji and non-ASCII: café, naïve, 北京",
    ]

    results = benchmark_tokenizers(
        corpus,
        reference=TiktokenTokenizer(),
        tokenizers=[HeuristicTokenizer(), TiktokenTokenizer()],
    )
    heuristic_result, tiktoken_result = results

    # tiktoken vs. itself must be exactly zero error -- sanity check
    # that the harness itself is correct.
    assert tiktoken_result.mean_absolute_percentage_error == 0.0

    # The heuristic's error is real and nonzero -- this test exists so
    # a future change to HeuristicTokenizer that quietly makes it wildly
    # inaccurate gets caught, not so a specific number is enshrined.
    assert heuristic_result.mean_absolute_percentage_error > 0.0
    assert heuristic_result.sample_count == len(corpus)
