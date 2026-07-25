"""Tests for the LLMProvider protocol itself, independent of any specific implementation."""
from contextshift.llm import GroqProvider, LLMProvider
from fakes import FakeLLMProvider


def test_fake_provider_satisfies_llm_provider_protocol():
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_groq_provider_satisfies_llm_provider_protocol():
    assert isinstance(GroqProvider(api_key="test-key"), LLMProvider)


def test_something_lacking_complete_and_stream_does_not_satisfy_protocol():
    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), LLMProvider)


def test_a_fake_provider_validates_the_interface_is_satisfiable_without_transport_complexity():
    # The point of FakeLLMProvider existing at all: if a ~15-line
    # in-memory class can conform to LLMProvider cleanly, with none of
    # GroqProvider's HTTP/retry/streaming-parse machinery, that's a
    # signal the interface drew the right line between "a provider" and
    # "everything else."
    from contextshift.core import Message

    provider = FakeLLMProvider(complete_response="hello")
    result = provider.complete([Message(role="user", content="hi")])

    assert result == "hello"
    assert provider.complete_calls == [([Message(role="user", content="hi")], 1024)]
