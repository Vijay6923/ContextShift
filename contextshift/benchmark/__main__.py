"""
CLI entry point: `python -m contextshift.benchmark --suite {standard,needle,tokenizer}`.

Exists so every benchmark claim in README.md and docs/decisions/ is
reproducible with one command instead of "trust the number in the
table" -- the same discipline ADR 0013 (needle retention) and ADR 0014
(tokenizer accuracy) already hold every number in this project to.

All three suites are deterministic and network-free: `standard` and
`needle` run against the real, committed fixture suite
(tests/fixtures/conversations/); `tokenizer` needs the optional
`tiktoken` extra (`pip install contextshift[tiktoken]`) since it's
comparing against a real tokenizer, not calling one over the network.
This module is deliberately not part of `contextshift.benchmark`'s
public `__all__` -- it's an entry point (`python -m ...`), not a
library import.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contextshift.benchmark import (
    ConversationFixture,
    benchmark_tokenizers,
    load_fixtures,
    run_benchmark,
    run_needle_benchmark,
    to_markdown,
    tokenizer_benchmark_to_markdown,
)
from contextshift.core import TokenBudget
from contextshift.strategies import PinnedRecencyStrategy, RecencyStrategy, SlidingWindowStrategy
from contextshift.tokenizers import HeuristicTokenizer

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "conversations"

# The exact defaults docs/decisions/0013-needle-retention-benchmark.md's
# published table and README.md's needle-retention table were measured
# with -- `--suite needle` with no other flags reproduces them exactly.
_NEEDLE_DEFAULT_MAX_TOKENS = 350
_NEEDLE_DEFAULT_SAFETY_MARGIN = 50

# A larger, separate budget for `standard` -- the classic
# messages/tokens-kept table is illustrative rather than tied to one
# canonical published number, so it defaults to something that shows
# meaningful pruning across the full concatenated fixture conversation
# (49 fixtures, ~2200 messages) rather than mirroring `needle`'s
# tighter, per-fixture budget.
_STANDARD_DEFAULT_MAX_TOKENS = 8000
_STANDARD_DEFAULT_SAFETY_MARGIN = 500

# The exact corpus docs/decisions/0014-accurate-tokenizers.md's
# published table was measured with -- see
# tests/test_tokenizer_bench.py::test_heuristic_tokenizer_error_rate_against_tiktoken_is_measured_not_assumed,
# which this mirrors so both stay reproducible from the same source.
_TOKENIZER_CORPUS = [
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


def _strategies() -> list[RecencyStrategy | SlidingWindowStrategy | PinnedRecencyStrategy]:
    return [RecencyStrategy(), SlidingWindowStrategy(window_size=10), PinnedRecencyStrategy(recent_buffer=6)]


def _load_fixtures_or_exit() -> list[ConversationFixture]:
    fixtures = load_fixtures(FIXTURES_DIR)
    if not fixtures:
        raise SystemExit(f"No fixtures found in {FIXTURES_DIR}")
    return fixtures


def _run_standard(max_tokens: int | None, safety_margin: int | None) -> str:
    fixtures = _load_fixtures_or_exit()
    conversation = [m for f in fixtures for m in f.messages]
    budget = TokenBudget(
        max_tokens=max_tokens if max_tokens is not None else _STANDARD_DEFAULT_MAX_TOKENS,
        safety_margin=safety_margin if safety_margin is not None else _STANDARD_DEFAULT_SAFETY_MARGIN,
    )
    results = run_benchmark(conversation, budget, _strategies())
    return to_markdown(results)


def _run_needle(max_tokens: int | None, safety_margin: int | None) -> str:
    fixtures = _load_fixtures_or_exit()
    budget = TokenBudget(
        max_tokens=max_tokens if max_tokens is not None else _NEEDLE_DEFAULT_MAX_TOKENS,
        safety_margin=safety_margin if safety_margin is not None else _NEEDLE_DEFAULT_SAFETY_MARGIN,
    )
    results = run_needle_benchmark(fixtures, budget, _strategies())
    return to_markdown(results)


def _run_tokenizer() -> str:
    try:
        from contextshift.tokenizers import TiktokenTokenizer
    except ImportError as exc:
        raise SystemExit(
            "The 'tokenizer' suite requires the optional tiktoken dependency: "
            "pip install contextshift[tiktoken]"
        ) from exc

    results = benchmark_tokenizers(
        _TOKENIZER_CORPUS,
        reference=TiktokenTokenizer(),
        tokenizers=[HeuristicTokenizer(), TiktokenTokenizer()],
    )
    return tokenizer_benchmark_to_markdown(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m contextshift.benchmark",
        description=(
            "Run one of contextshift's deterministic benchmark suites against the "
            "real fixture suite in tests/fixtures/conversations/, and print the "
            "result as a Markdown table."
        ),
    )
    parser.add_argument(
        "--suite",
        choices=["standard", "needle", "tokenizer"],
        default="standard",
        help="Which suite to run (default: standard).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="TokenBudget.max_tokens for 'standard'/'needle' (defaults: 8000 standard, 350 needle).",
    )
    parser.add_argument(
        "--safety-margin",
        type=int,
        default=None,
        help="TokenBudget.safety_margin for 'standard'/'needle' (defaults: 500 standard, 50 needle).",
    )
    args = parser.parse_args(argv)

    if args.suite == "standard":
        print(_run_standard(args.max_tokens, args.safety_margin))
    elif args.suite == "needle":
        print(_run_needle(args.max_tokens, args.safety_margin))
    else:
        print(_run_tokenizer())
    return 0


if __name__ == "__main__":
    sys.exit(main())
