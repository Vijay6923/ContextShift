"""
Direct side-by-side comparison of utils.token_manager.estimate_tokens
(legacy, still what the running application uses) against
contextshift.tokenizers.heuristic (new, not wired into the application
yet), over a representative corpus of inputs.

This is deliberately not just "the new code has its own tests passing" --
it's a behavioral-equivalence check between the two implementations, run
before any cutover, so a transcription slip during the port would be
caught here even if each side's own tests happened to pass in isolation.
"""
import pytest

from contextshift.tokenizers.heuristic import HeuristicTokenizer
from contextshift.tokenizers.heuristic import estimate_tokens as new_estimate_tokens
from utils.token_manager import estimate_tokens as legacy_estimate_tokens

QUALITATIVE_CORPUS = [
    "",
    " ",
    "   ",
    "\t",
    "\n",
    "\n\n  \t ",
    "a",
    "I",
    "hello",
    "hello world",
    "the quick brown fox jumps over the lazy dog",
    "Hello, world! How are you?",
    "The answer is 42.",
    "hello\n\nworld   foo",
    "  hello world  ",
    "Hello \U0001F44B world \U0001F30D",  # emoji, non-ASCII
    "!!!",
    "...",
    "https://example.com/very/long/path/that/is/one/token",
    "[SUMMARY] The user asked about Python decorators and the assistant explained closures.",
    "\U0001F4C4 **PDF Uploaded: doc.pdf**\n\n---\n*Extracted PDF content:*\nSome extracted text here.",
    "\U0001F5BC️ **Image Uploaded: photo.png**\n\nPlease analyze this image.",
    "word " * 500,  # long content, mirrors a large pasted document
]

# Exhaustive sweep of word counts 0-100, to pin down the max(1, int(n*1.3))
# truncation formula across a wide numeric range, not just a few examples.
WORD_COUNT_SWEEP = [" ".join(["word"] * n) for n in range(0, 101)]


@pytest.mark.parametrize("text", QUALITATIVE_CORPUS)
def test_new_heuristic_matches_legacy_on_qualitative_corpus(text):
    assert new_estimate_tokens(text) == legacy_estimate_tokens(text)


@pytest.mark.parametrize("text", WORD_COUNT_SWEEP)
def test_new_heuristic_matches_legacy_across_word_count_sweep(text):
    assert new_estimate_tokens(text) == legacy_estimate_tokens(text)


def test_heuristic_tokenizer_class_matches_free_function_on_full_corpus():
    tokenizer = HeuristicTokenizer()
    for text in QUALITATIVE_CORPUS + WORD_COUNT_SWEEP:
        assert tokenizer.estimate_tokens(text) == new_estimate_tokens(text)
