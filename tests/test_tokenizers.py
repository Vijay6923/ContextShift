"""Tests for the Tokenizer protocol and its implementations, independent of the legacy comparison."""
import warnings

import pytest

import contextshift.tokenizers.heuristic as heuristic_module
from contextshift.tokenizers import HeuristicTokenizer, HeuristicTokenizerAccuracyWarning, Tokenizer


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


# -- HeuristicTokenizerAccuracyWarning (docs/decisions/0017) ----------------
#
# _warned is a process-global flag (deliberately not per-instance or
# per-call-site -- see the ADR for why), so these tests reset it via
# monkeypatch rather than relying on being the first thing in the suite
# to construct a HeuristicTokenizer.


def test_constructing_heuristic_tokenizer_warns_once(monkeypatch):
    monkeypatch.setattr(heuristic_module, "_warned", False)

    with pytest.warns(HeuristicTokenizerAccuracyWarning, match="tiktoken"):
        HeuristicTokenizer()


def test_constructing_heuristic_tokenizer_a_second_time_does_not_warn_again(monkeypatch):
    monkeypatch.setattr(heuristic_module, "_warned", False)

    with pytest.warns(HeuristicTokenizerAccuracyWarning):
        HeuristicTokenizer()

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning here fails the test
        HeuristicTokenizer()  # should not warn -- already warned above


def test_heuristic_tokenizer_accuracy_warning_can_be_filtered(monkeypatch):
    monkeypatch.setattr(heuristic_module, "_warned", False)

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any *other* warning still fails the test
        warnings.filterwarnings("ignore", category=HeuristicTokenizerAccuracyWarning)
        HeuristicTokenizer()  # silently suppressed, not an error
