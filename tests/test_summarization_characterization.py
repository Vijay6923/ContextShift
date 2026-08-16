"""
Direct comparison between the legacy tests.fixtures.legacy.summarizer.summarize_messages
(the pre-refactor implementation, kept only as a characterization
fixture -- see tests/fixtures/legacy/__init__.py) and the new
contextshift.summarization.Summarizer, verifying they construct the
identical prompt (system message + conversation transcript) and forward
the same max_tokens.

Each side's underlying provider call is mocked/faked rather than hitting
a real network -- this compares *prompt construction*, which is what
Step 6 actually changed. The provider call itself (HTTP, retries,
streaming) was already verified independently in
test_llm_characterization.py (Step 5) and isn't re-verified here.

contextshift.core.Message duck-types cleanly against what legacy's
summarize_messages reads (.role, .content), so the same instances are
fed to both implementations directly, exactly as in the Step 4 strategy
comparison.
"""
from contextshift.core import Message
from contextshift.summarization import Summarizer
from contextshift.testing import FakeLLMProvider
from tests.fixtures.legacy import summarizer as legacy

SCENARIOS = {
    "typical_exchange": [
        Message(role="user", content="What's the capital of France?"),
        Message(role="assistant", content="Paris."),
        Message(role="user", content="And Germany?"),
        Message(role="assistant", content="Berlin."),
    ],
    "includes_a_system_role_message": [
        Message(role="user", content="Remember my name is Alex."),
        Message(role="system", content="[SUMMARY] An earlier summary."),
        Message(role="assistant", content="Got it, Alex."),
    ],
    "single_message": [Message(role="user", content="hello")],
    "empty_conversation": [],
}


def test_new_summarizer_prompt_matches_legacy_across_scenarios(monkeypatch):
    for name, messages in SCENARIOS.items():
        captured_legacy = {}

        def fake_call_groq(prompt_messages, max_tokens=1024):
            captured_legacy["messages"] = prompt_messages
            captured_legacy["max_tokens"] = max_tokens
            return "A dense summary."

        monkeypatch.setattr("tests.fixtures.legacy.summarizer.call_groq", fake_call_groq)

        legacy_result = legacy.summarize_messages(messages)

        fake_provider = FakeLLMProvider(complete_response="A dense summary.")
        new_result = Summarizer(fake_provider).summarize(messages)

        assert legacy_result == new_result == "A dense summary.", name

        new_messages, new_max_tokens = fake_provider.complete_calls[0]
        reconstructed = [{"role": m.role, "content": m.content} for m in new_messages]

        assert captured_legacy["messages"] == reconstructed, name
        assert captured_legacy["max_tokens"] == new_max_tokens == 512, name
