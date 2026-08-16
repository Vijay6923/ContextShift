"""tiktoken-backed tokenizer -- an actual byte-pair-encoding tokenizer, not a heuristic. Optional dependency."""
from __future__ import annotations

DEFAULT_ENCODING = "cl100k_base"


class TiktokenTokenizer:
    """
    A Tokenizer (contextshift.tokenizers.base.Tokenizer) backed by
    OpenAI's `tiktoken` library -- a real byte-pair-encoding
    tokenizer, not `HeuristicTokenizer`'s word-count approximation.

    Optional dependency: install with `pip install contextshift[tiktoken]`.
    The `tiktoken` import is deferred to construction time, not module
    import time -- `from contextshift.tokenizers import TiktokenTokenizer`
    always succeeds even without `tiktoken` installed; only
    constructing an instance requires it, with a clear error naming
    the install command if it's missing, rather than a bare
    `ModuleNotFoundError` a caller has to guess the fix for.

    Args:
        encoding_name: Which tiktoken encoding to use. Defaults to
            `"cl100k_base"` -- not because this library is
            OpenAI-specific, but because it's tiktoken's own
            widely-applicable general-purpose encoding, a reasonable
            default for "count roughly the way a modern subword
            tokenizer would" even against a non-OpenAI model's output.
            Override this if you specifically need a different
            encoding tiktoken supports.
    """

    def __init__(self, encoding_name: str = DEFAULT_ENCODING) -> None:
        try:
            import tiktoken
        except ImportError as exc:
            raise ImportError(
                "TiktokenTokenizer requires the 'tiktoken' package. "
                "Install it with: pip install contextshift[tiktoken]"
            ) from exc
        self._encoding = tiktoken.get_encoding(encoding_name)

    def estimate_tokens(self, text: str) -> int:
        # tiktoken already returns an empty token list for "", so no
        # separate empty-string guard is needed here.
        return len(self._encoding.encode(text))
