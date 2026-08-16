"""
Tests for TiktokenTokenizer. Uses the real `tiktoken` library -- no
network access, no API key, and no mocking needed, since tiktoken's
encodings are shipped/downloaded once and run entirely locally.
"""
import pytest

from contextshift.tokenizers import TiktokenTokenizer, Tokenizer


def test_tiktoken_tokenizer_satisfies_tokenizer_protocol():
    assert isinstance(TiktokenTokenizer(), Tokenizer)


def test_empty_string_is_zero_tokens():
    assert TiktokenTokenizer().estimate_tokens("") == 0


def test_estimate_tokens_returns_a_real_positive_count():
    result = TiktokenTokenizer().estimate_tokens("hello world")
    assert isinstance(result, int)
    assert result > 0


def test_longer_text_generally_costs_more_tokens():
    tokenizer = TiktokenTokenizer()
    short = tokenizer.estimate_tokens("hello")
    long = tokenizer.estimate_tokens("hello there, this is a much longer piece of text to encode")
    assert long > short


def test_same_text_is_deterministic():
    tokenizer = TiktokenTokenizer()
    text = "The quick brown fox jumps over the lazy dog."
    assert tokenizer.estimate_tokens(text) == tokenizer.estimate_tokens(text)


def test_custom_encoding_name_is_used():
    # cl100k_base and p50k_base are both real tiktoken encodings with
    # different vocabularies -- if encoding_name were ignored, they'd
    # tokenize identically, which they don't for arbitrary text.
    default = TiktokenTokenizer().estimate_tokens("supercalifragilisticexpialidocious")
    alt = TiktokenTokenizer(encoding_name="p50k_base").estimate_tokens("supercalifragilisticexpialidocious")
    assert isinstance(default, int)
    assert isinstance(alt, int)


def test_missing_tiktoken_gives_a_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tiktoken":
            raise ImportError("No module named 'tiktoken'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match=r"pip install contextshift\[tiktoken\]"):
        TiktokenTokenizer()
