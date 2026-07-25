"""Word-count heuristic tokenizer, ported mechanically from the original application."""
from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """
    Approximate the token count of `text` using a word-count heuristic.

    Formula, verbatim from the original application: falsy input (only
    `None` or the empty string -- a non-empty whitespace-only string is
    *not* falsy) returns 0; otherwise, `max(1, int(word_count * 1.3))`,
    where `word_count` comes from Python's `str.split()` with no
    arguments (splits on runs of whitespace, discards leading/trailing
    whitespace). One consequence worth naming explicitly because it's
    easy to get wrong porting this by hand: a non-empty whitespace-only
    string (e.g. `"   "`) has `word_count == 0` but is *not* caught by
    the falsy check, so it returns `max(1, 0) == 1`, not 0.

    This is a rough, non-model-specific approximation, not a real
    tokenizer -- it exists because the original application never
    depended on one. It is ported here unchanged, formula and edge cases
    included, deliberately rather than out of an inability to improve it;
    see tests/test_tokenizer_characterization.py for a direct comparison
    against the original implementation over a representative corpus.

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
    heuristic be used polymorphically anywhere a Tokenizer is expected
    (e.g. passed into a future strategy), rather than callers depending
    on this specific free function.
    """

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text)
