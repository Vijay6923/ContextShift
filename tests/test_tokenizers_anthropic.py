"""
Tests for AnthropicTokenizer. The Anthropic client is mocked throughout
-- no network access, no real API key needed, matching the pattern
already established for GroqProvider and GeminiVisionProvider.

Not live-verified against a real Anthropic API key in this session --
built and tested to the SDK's documented shape
(`client.messages.count_tokens(...) -> MessageTokensCount` with an
`input_tokens` field, confirmed by inspecting the installed `anthropic`
package directly), the same level of confidence GroqProvider had
before its first live call, not the same level of confidence it has
after. Worth a live check before this is relied on for a real budget
decision.
"""
import pytest

from contextshift.tokenizers import AnthropicTokenizer, Tokenizer


class _FakeCountResponse:
    def __init__(self, input_tokens):
        self.input_tokens = input_tokens


class _FakeMessages:
    def __init__(self, input_tokens=7):
        self._input_tokens = input_tokens
        self.calls = []

    def count_tokens(self, *, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return _FakeCountResponse(self._input_tokens)


class _FakeAnthropicClient:
    def __init__(self, *args, **kwargs):
        self.messages = _FakeMessages()


def _install_fake_client(monkeypatch, input_tokens=7):
    fake_client = _FakeAnthropicClient()
    fake_client.messages = _FakeMessages(input_tokens=input_tokens)

    class _Client:
        def __new__(cls, *args, **kwargs):
            return fake_client

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    return fake_client


def test_requires_api_key_at_construction():
    with pytest.raises(ValueError, match="api_key is required"):
        AnthropicTokenizer(api_key="")


def test_satisfies_tokenizer_protocol(monkeypatch):
    _install_fake_client(monkeypatch)
    assert isinstance(AnthropicTokenizer(api_key="k"), Tokenizer)


def test_empty_string_is_zero_tokens_with_no_network_call(monkeypatch):
    fake_client = _install_fake_client(monkeypatch)
    result = AnthropicTokenizer(api_key="k").estimate_tokens("")
    assert result == 0
    assert fake_client.messages.calls == []


def test_returns_input_tokens_from_the_sdk_response(monkeypatch):
    _install_fake_client(monkeypatch, input_tokens=42)
    result = AnthropicTokenizer(api_key="k").estimate_tokens("hello world")
    assert result == 42


def test_sends_text_as_a_single_user_message(monkeypatch):
    fake_client = _install_fake_client(monkeypatch)
    AnthropicTokenizer(api_key="k").estimate_tokens("hello world")

    call = fake_client.messages.calls[0]
    assert call["messages"] == [{"role": "user", "content": "hello world"}]


def test_uses_configured_model(monkeypatch):
    fake_client = _install_fake_client(monkeypatch)
    AnthropicTokenizer(api_key="k", model="claude-3-5-haiku-latest").estimate_tokens("hi")

    assert fake_client.messages.calls[0]["model"] == "claude-3-5-haiku-latest"


def test_missing_anthropic_sdk_gives_a_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match=r"pip install contextshift\[anthropic\]"):
        AnthropicTokenizer(api_key="k")
