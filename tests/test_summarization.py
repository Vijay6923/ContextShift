"""
Unit tests for Summarizer using FakeLLMProvider -- no network calls, no
GroqProvider. Direct comparison against the legacy implementation lives
in test_summarization_characterization.py.
"""
import pytest

import contextshift.summarization.summarizer as summarizer_module
from contextshift.core import Message
from contextshift.summarization import DEFAULT_MAX_TOKENS, Summarizer
from fakes import FakeLLMProvider


def test_summarize_returns_providers_response_unmodified():
    fake = FakeLLMProvider(complete_response="A dense paragraph.")
    result = Summarizer(fake).summarize([Message(role="user", content="hi")])

    assert result == "A dense paragraph."


def test_summarize_uses_default_max_tokens_of_512():
    fake = FakeLLMProvider()
    Summarizer(fake).summarize([Message(role="user", content="hi")])

    _, max_tokens = fake.complete_calls[0]
    assert max_tokens == DEFAULT_MAX_TOKENS == 512


def test_max_tokens_is_configurable():
    fake = FakeLLMProvider()
    Summarizer(fake, max_tokens=100).summarize([Message(role="user", content="hi")])

    _, max_tokens = fake.complete_calls[0]
    assert max_tokens == 100


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_max_tokens_must_be_positive(max_tokens):
    with pytest.raises(ValueError, match="max_tokens"):
        Summarizer(FakeLLMProvider(), max_tokens=max_tokens)


def test_prompt_sent_to_provider_has_system_message_and_transcript():
    fake = FakeLLMProvider()
    Summarizer(fake).summarize(
        [
            Message(role="user", content="What's the capital of France?"),
            Message(role="assistant", content="Paris."),
        ]
    )

    sent_messages, _ = fake.complete_calls[0]
    assert len(sent_messages) == 2
    assert sent_messages[0].role == "system"
    assert "summarizer" in sent_messages[0].content.lower()
    assert sent_messages[1].role == "user"
    assert sent_messages[1].content == "user: What's the capital of France?\nassistant: Paris.\n"


def test_non_user_roles_are_transcribed_as_assistant():
    # Direct port of legacy's `role = "user" if msg.role == "user" else
    # "assistant"` -- a "system" role message is transcribed as if the
    # assistant said it. Preserved, not fixed; see ADR 0007.
    fake = FakeLLMProvider()
    Summarizer(fake).summarize([Message(role="system", content="A pinned instruction.")])

    sent_messages, _ = fake.complete_calls[0]
    assert sent_messages[1].content == "assistant: A pinned instruction.\n"


def test_does_not_add_a_summary_label_to_the_output():
    fake = FakeLLMProvider(complete_response="Plain summary text.")
    result = Summarizer(fake).summarize([Message(role="user", content="hi")])

    assert result == "Plain summary text."
    assert "[SUMMARY]" not in result


def test_summarizing_empty_message_list_does_not_raise():
    # Legacy never guarded against this either -- the "not enough
    # messages" check lived in the Flask route, not in
    # summarize_messages() itself. Preserving that permissiveness here.
    fake = FakeLLMProvider(complete_response="(nothing to summarize)")
    result = Summarizer(fake).summarize([])

    assert result == "(nothing to summarize)"
    sent_messages, _ = fake.complete_calls[0]
    assert sent_messages[1].content == ""


def test_never_imports_groq_provider():
    # Checks the module's actual namespace, not its source text -- the
    # word "Groq" legitimately appears in this module's own docstrings
    # (explaining what it deliberately does NOT depend on), which a
    # naive text scan would misreport as a violation.
    assert "GroqProvider" not in vars(summarizer_module)
    assert not any("groq" in name.lower() for name in vars(summarizer_module))
