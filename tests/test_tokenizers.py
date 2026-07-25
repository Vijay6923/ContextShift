"""Tests for the Tokenizer protocol and its implementations, independent of the legacy comparison."""
from contextshift.tokenizers import HeuristicTokenizer, Tokenizer


def test_heuristic_tokenizer_satisfies_tokenizer_protocol():
    assert isinstance(HeuristicTokenizer(), Tokenizer)


def test_something_lacking_estimate_tokens_does_not_satisfy_protocol():
    class NotATokenizer:
        pass

    assert not isinstance(NotATokenizer(), Tokenizer)


def test_anything_with_matching_method_satisfies_protocol_structurally():
    # Protocol conformance is structural, not inheritance-based -- a future
    # tiktoken-backed or provider-native tokenizer satisfies Tokenizer just
    # by having a matching method, with no dependency on this package.
    class DuckTypedTokenizer:
        def estimate_tokens(self, text: str) -> int:
            return len(text)

    assert isinstance(DuckTypedTokenizer(), Tokenizer)


def test_heuristic_tokenizer_is_stateless_and_reusable():
    tokenizer = HeuristicTokenizer()
    first = tokenizer.estimate_tokens("hello world")
    second = tokenizer.estimate_tokens("hello world")
    assert first == second
