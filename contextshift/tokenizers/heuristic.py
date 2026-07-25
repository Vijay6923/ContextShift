"""Word-count heuristic tokenizer."""
from __future__ import annotations


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
    tokenization. Use it for a cheap estimate; use a model-specific
    tokenizer (e.g. tiktoken, or a provider's own counting endpoint) when
    accuracy matters more than speed.

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
    """

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text)
