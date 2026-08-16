"""Tests for contextshift.testing.FakeSummarizer, independent of any strategy that consumes it."""
from contextshift.core import Message
from contextshift.summarization import Summarizer
from contextshift.testing import FakeSummarizer


def test_fake_summarizer_is_a_real_summarizer():
    # A genuine subclass, not a lookalike -- see FakeSummarizer's
    # docstring for why this matters (isinstance checks, type hints).
    assert isinstance(FakeSummarizer(), Summarizer)


def test_fake_summarizer_returns_its_configured_text_regardless_of_input():
    fake = FakeSummarizer("a fixed summary")

    result = fake.summarize([Message(role="user", content="anything at all")])

    assert result == "a fixed summary"


def test_fake_summarizer_defaults_to_an_unmistakably_fake_placeholder():
    fake = FakeSummarizer()

    result = fake.summarize([Message(role="user", content="hi")])

    assert result == "[FAKE SUMMARY]"


def test_fake_summarizer_is_deterministic_across_different_inputs():
    fake = FakeSummarizer("stable")

    first = fake.summarize([Message(role="user", content="one")])
    second = fake.summarize([Message(role="assistant", content="something totally different")])

    assert first == second == "stable"


def test_fake_summarizer_makes_no_network_calls():
    # No HTTP client, no API key, no environment lookup -- purely an
    # in-memory FakeLLMProvider one level down. Constructing and calling
    # it succeeding at all, with zero configuration, is the proof.
    fake = FakeSummarizer()
    fake.summarize([])
