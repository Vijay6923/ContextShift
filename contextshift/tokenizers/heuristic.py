"""Word-count heuristic tokenizer."""
from __future__ import annotations

import warnings

_warned = False


class HeuristicTokenizerAccuracyWarning(UserWarning):
    """
    Warned once per process, the first time HeuristicTokenizer is
    constructed -- see
    docs/decisions/0017-heuristic-tokenizer-safety-default.md for why,
    and how to suppress it deliberately:

        warnings.filterwarnings("ignore", category=HeuristicTokenizerAccuracyWarning)
    """


def estimate_tokens(text: str) -> int:
    """
    Approximate the token count of `text` using a word-count heuristic.

    Formula: falsy input (only `None` or the empty string -- a non-empty
    whitespace-only string is *not* falsy) returns 0; otherwise,
    `max(1, int(word_count * 1.3))`, where `word_count` comes from
    Python's `str.split()` with no arguments (splits on runs of
    whitespace, discards leading/trailing whitespace). One consequence
    worth naming explicitly: a non-empty whitespace-only string (e.g.
    `"   "`) has `word_count == 0` but is *not* caught by the falsy
    check, so it returns `max(1, 0) == 1`, not 0.

    This is a rough, non-model-specific approximation, not a real
    tokenizer -- it doesn't correspond to any particular model's actual
    tokenization. Its actual error rate is measured, not just implied:
    ~28% mean error against a real tokenizer, worst case near 100% on
    a single sample -- see
    docs/decisions/0014-accurate-tokenizers.md and
    tests/test_tokenizer_bench.py for the corpus and the number. Use
    this for a cheap, zero-dependency estimate; use
    `contextshift.tokenizers.TiktokenTokenizer` or `AnthropicTokenizer`
    when accuracy matters more than speed or dependency footprint.

    Args:
        text: The text to measure. Not validated or normalized in any way.

    Returns:
        The estimated token count. Never negative; 0 only for falsy input.
    """
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.3))


class HeuristicTokenizer:
    """
    A Tokenizer (contextshift.tokenizers.base.Tokenizer) backed by the
    word-count heuristic in `estimate_tokens` above.

    Stateless -- holds no configuration -- so it exists purely to let the
    heuristic be used polymorphically anywhere a Tokenizer is expected,
    rather than callers depending on this specific free function.

    Constructing this class warns once per process
    (`HeuristicTokenizerAccuracyWarning`) -- this is the library's
    zero-dependency default, silently used unless a caller picks
    otherwise, backing an estimate with a measured ~28% mean error and
    a worst case near 100% (docs/decisions/0014-accurate-tokenizers.md).
    A caller who has deliberately chosen this tradeoff can suppress the
    warning; see docs/decisions/0017-heuristic-tokenizer-safety-default.md.
    """

    def __init__(self) -> None:
        global _warned
        if not _warned:
            _warned = True
            warnings.warn(
                "HeuristicTokenizer estimates tokens with a word-count "
                "heuristic, not a real tokenizer -- measured ~28% mean error "
                "against tiktoken, worst case near 100% on a single input "
                "(docs/decisions/0014-accurate-tokenizers.md). For "
                "budget-critical use, prefer TiktokenTokenizer "
                "(pip install contextshift[tiktoken]) or AnthropicTokenizer "
                "(pip install contextshift[anthropic]). See "
                "docs/decisions/0017-heuristic-tokenizer-safety-default.md "
                "for the full reasoning, or filter "
                "HeuristicTokenizerAccuracyWarning to silence this.",
                category=HeuristicTokenizerAccuracyWarning,
                stacklevel=2,
            )

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text)
