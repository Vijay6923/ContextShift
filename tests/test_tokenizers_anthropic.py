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


def test_retries_and_succeeds_after_a_connection_error(monkeypatch):
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages/count_tokens")
    fake_client = _install_fake_client(monkeypatch)
    calls = fake_client.messages.calls
    real_count_tokens = fake_client.messages.count_tokens
    attempt = {"n": 0}

    def flaky_count_tokens(*, model, messages):
        attempt["n"] += 1
        if attempt["n"] == 1:
            raise anthropic.APIConnectionError(request=request)
        return real_count_tokens(model=model, messages=messages)

    fake_client.messages.count_tokens = flaky_count_tokens
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    result = AnthropicTokenizer(api_key="k").estimate_tokens("hello")

    assert result == 7  # default fake input_tokens
    assert attempt["n"] == 2  # failed once, succeeded on retry
    assert len(calls) == 1  # only the successful call reached real_count_tokens


def test_raises_a_friendly_exception_after_exhausting_retries(monkeypatch):
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages/count_tokens")
    fake_client = _install_fake_client(monkeypatch)

    def always_fails(*, model, messages):
        raise anthropic.APIConnectionError(request=request)

    fake_client.messages.count_tokens = always_fails
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    with pytest.raises(Exception, match="Failed to count tokens with Anthropic"):
        AnthropicTokenizer(api_key="k").estimate_tokens("hello")


def test_raises_a_friendly_exception_on_rate_limit(monkeypatch):
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages/count_tokens")
    response = httpx.Response(429, request=request)
    fake_client = _install_fake_client(monkeypatch)

    def always_rate_limited(*, model, messages):
        raise anthropic.RateLimitError("rate limited", response=response, body=None)

    fake_client.messages.count_tokens = always_rate_limited
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    with pytest.raises(Exception, match="Anthropic rate limit reached"):
        AnthropicTokenizer(api_key="k").estimate_tokens("hello")


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
