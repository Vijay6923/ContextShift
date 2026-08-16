"""Anthropic-native tokenizer, via Anthropic's own token-counting endpoint. Optional dependency, network call."""
from __future__ import annotations

import time

DEFAULT_MODEL = "claude-3-5-sonnet-latest"

_MAX_RETRIES = 3
_BASE_BACKOFF = 5  # seconds


class AnthropicTokenizer:
    """
    A Tokenizer (contextshift.tokenizers.base.Tokenizer) backed by
    Anthropic's own token-counting endpoint (`client.messages.count_tokens`)
    -- the exact count a Claude model would compute, not an
    approximation of one.

    Unlike `HeuristicTokenizer` and `TiktokenTokenizer`, this makes a
    real network call on every `estimate_tokens()` call -- there is no
    local Claude tokenizer to run offline, the same reason
    `GeminiVisionProvider` needs a network call to do its job. This is
    an accepted, real trade-off, not an oversight: exact Claude token
    counts require asking Anthropic. Do not use this inside a tight
    loop, or inside a benchmark that's meant to stay network-free
    (contextshift.benchmark's deterministic tier never does).

    Retries on failure (rate limit or connection error) up to 3 times
    with backoff, then raises a plain `Exception` with a human-readable
    message -- the same resilience `GroqProvider` and
    `GeminiVisionProvider` already provide, rather than letting a raw
    `anthropic` SDK exception propagate uncaught.

    Optional dependency: install with `pip install contextshift[anthropic]`.
    The `anthropic` import is deferred to construction time, matching
    `TiktokenTokenizer`'s pattern -- importing this class never
    requires the SDK to be installed; constructing one does.

    Args:
        api_key: Anthropic API key. Required, and validated at
            construction time, matching every other network-calling
            class in this library (`GroqProvider`, `GeminiVisionProvider`).
            Not read from any global configuration -- contextshift
            never imports application configuration directly (see
            docs/decisions/0001-library-independence-and-adapter-placement.md).
        model: Which Claude model's tokenizer to count against -- token
            boundaries can differ slightly between model families, so
            this should match whichever model you're actually about to
            call. Defaults to `"claude-3-5-sonnet-latest"`; override
            for a different model.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "AnthropicTokenizer requires the 'anthropic' package. "
                "Install it with: pip install contextshift[anthropic]"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0

        import anthropic

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.messages.count_tokens(
                    model=self._model,
                    messages=[{"role": "user", "content": text}],
                )
                return response.input_tokens

            except anthropic.RateLimitError as e:
                print(f"[ANTHROPIC TOKENIZER] Rate limited (attempt {attempt}/{_MAX_RETRIES}): {e}")
                if attempt == _MAX_RETRIES:
                    raise Exception("Anthropic rate limit reached. Please wait a moment and try again.") from e
                time.sleep(_BASE_BACKOFF * attempt)

            except anthropic.APIError as e:
                print(f"[ANTHROPIC TOKENIZER ERROR] attempt {attempt}: {e}")
                if attempt == _MAX_RETRIES:
                    raise Exception(f"Failed to count tokens with Anthropic: {e}") from e
                time.sleep(_BASE_BACKOFF * attempt)

        raise Exception("Anthropic token-counting request failed after maximum retries.")
