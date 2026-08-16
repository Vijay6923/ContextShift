"""
Direct comparison between the legacy tests.fixtures.legacy.summarizer
(call_groq, call_groq_stream -- the pre-refactor implementation, kept
only as a characterization fixture) and the new
contextshift.llm.groq.GroqProvider, with requests.post mocked so
neither side makes a real network call.

Both implementations call `requests.post` as an attribute of the same
shared `requests` module object, so patching `requests.post` once
affects both -- no separate mocking setup per side, which is what makes
a true side-by-side comparison possible here, the same way Message
duck-typing made the Step 4 strategy comparison possible.
"""
import json
import time

import pytest
import requests

from contextshift.core import Message
from contextshift.llm.groq import GroqProvider
from tests.fixtures.legacy import summarizer as legacy
from tests.fixtures.legacy.config import Config


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # Retry backoff sleeps for real seconds in both implementations;
    # nothing in this file should actually wait on the clock.
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, lines=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self._lines = lines or []
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error", response=self)

    def iter_lines(self):
        yield from self._lines


def _queue_responses(monkeypatch, responses):
    """Patch requests.post to return each response in order, on successive calls."""
    responses = list(responses)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=False):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout, "stream": stream})
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def _always_raise(monkeypatch, exc):
    def fake_post(*args, **kwargs):
        raise exc

    monkeypatch.setattr(requests, "post", fake_post)


def _sse_line(content=None, done=False):
    if done:
        return b"data: [DONE]"
    payload = json.dumps({"choices": [{"delta": {"content": content}}]})
    return f"data: {payload}".encode("utf-8")


NEW_MESSAGES = [Message(role="user", content="What's the capital of France?")]
LEGACY_MESSAGES = [{"role": "user", "content": "What's the capital of France?"}]


def _new_provider():
    return GroqProvider(api_key=Config.GROQ_API_KEY, model=Config.GROQ_MODEL, base_url=Config.GROQ_BASE_URL)


# -- complete() / call_groq -----------------------------------------------


def test_complete_happy_path_matches_legacy(monkeypatch):
    _queue_responses(
        monkeypatch, [_FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": "Paris."}}]})]
    )
    legacy_result = legacy.call_groq(LEGACY_MESSAGES, max_tokens=100)

    calls = _queue_responses(
        monkeypatch, [_FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": "Paris."}}]})]
    )
    new_result = _new_provider().complete(NEW_MESSAGES, max_tokens=100)

    assert legacy_result == new_result == "Paris."
    # Payload shape: complete()'s payload must never carry a "stream" key,
    # matching legacy's call_groq exactly (only call_groq_stream's does).
    sent_payload = calls[0]["json"]
    assert "stream" not in sent_payload
    assert sent_payload["messages"] == LEGACY_MESSAGES
    assert sent_payload["max_tokens"] == 100
    assert sent_payload["temperature"] == 0.7


def test_complete_retries_on_429_then_succeeds_matching_legacy(monkeypatch):
    def responses():
        return [
            _FakeResponse(status_code=429, headers={"Retry-After": "0"}),
            _FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": "Berlin."}}]}),
        ]

    _queue_responses(monkeypatch, responses())
    legacy_result = legacy.call_groq(LEGACY_MESSAGES, max_tokens=100)

    _queue_responses(monkeypatch, responses())
    new_result = _new_provider().complete(NEW_MESSAGES, max_tokens=100)

    assert legacy_result == new_result == "Berlin."


def test_complete_raises_after_max_429_retries_matching_legacy(monkeypatch):
    _queue_responses(monkeypatch, [_FakeResponse(status_code=429, headers={"Retry-After": "0"}) for _ in range(3)])
    with pytest.raises(Exception) as legacy_exc:
        legacy.call_groq(LEGACY_MESSAGES)

    _queue_responses(monkeypatch, [_FakeResponse(status_code=429, headers={"Retry-After": "0"}) for _ in range(3)])
    with pytest.raises(Exception) as new_exc:
        _new_provider().complete(NEW_MESSAGES)

    assert str(legacy_exc.value) == str(new_exc.value) == "Groq API request failed after maximum retries."


def test_complete_raises_after_connection_errors_matching_legacy(monkeypatch):
    _always_raise(monkeypatch, requests.exceptions.ConnectionError("boom"))
    with pytest.raises(Exception) as legacy_exc:
        legacy.call_groq(LEGACY_MESSAGES)

    _always_raise(monkeypatch, requests.exceptions.ConnectionError("boom"))
    with pytest.raises(Exception) as new_exc:
        _new_provider().complete(NEW_MESSAGES)

    assert str(legacy_exc.value) == str(new_exc.value)


def test_complete_gives_friendly_message_when_exception_text_mentions_429(monkeypatch):
    # A subtle, easy-to-miss branch: `if "429" in str(e)` inspects the
    # *exception's message text*, not the response status code -- 429
    # status codes are already handled earlier via the status-code check
    # and never reach this except block through raise_for_status(). This
    # branch only fires if requests.post() itself raises with "429"
    # somewhere in its message (e.g. certain connection-level errors),
    # which is a genuinely different trigger than an HTTP 429 response.
    exc = requests.exceptions.RequestException("Error 429: too many requests")

    _always_raise(monkeypatch, exc)
    with pytest.raises(Exception) as legacy_exc:
        legacy.call_groq(LEGACY_MESSAGES)

    _always_raise(monkeypatch, exc)
    with pytest.raises(Exception) as new_exc:
        _new_provider().complete(NEW_MESSAGES)

    assert (
        str(legacy_exc.value)
        == str(new_exc.value)
        == "Groq rate limit reached. Please wait a moment and try again."
    )


# -- stream() / call_groq_stream -------------------------------------------


def test_stream_happy_path_matches_legacy(monkeypatch):
    lines = [_sse_line("Hello"), _sse_line(" world"), _sse_line(done=True)]

    _queue_responses(monkeypatch, [_FakeResponse(status_code=200, lines=lines)])
    legacy_chunks = list(legacy.call_groq_stream(LEGACY_MESSAGES, max_tokens=100))

    calls = _queue_responses(monkeypatch, [_FakeResponse(status_code=200, lines=lines)])
    new_chunks = list(_new_provider().stream(NEW_MESSAGES, max_tokens=100))

    assert legacy_chunks == new_chunks == ["Hello", " world"]
    # Payload shape: stream()'s payload must carry "stream": True,
    # matching legacy's call_groq_stream exactly.
    sent_payload = calls[0]["json"]
    assert sent_payload["stream"] is True
    assert sent_payload["max_tokens"] == 100


def test_stream_skips_malformed_json_lines_matching_legacy(monkeypatch):
    lines = [
        _sse_line("Hello"),
        b"data: {not valid json",
        _sse_line(" world"),
        _sse_line(done=True),
    ]

    _queue_responses(monkeypatch, [_FakeResponse(status_code=200, lines=lines)])
    legacy_chunks = list(legacy.call_groq_stream(LEGACY_MESSAGES))

    _queue_responses(monkeypatch, [_FakeResponse(status_code=200, lines=lines)])
    new_chunks = list(_new_provider().stream(NEW_MESSAGES))

    assert legacy_chunks == new_chunks == ["Hello", " world"]


def test_stream_raises_after_connection_errors_matching_legacy(monkeypatch):
    _always_raise(monkeypatch, requests.exceptions.ConnectionError("boom"))
    with pytest.raises(Exception) as legacy_exc:
        list(legacy.call_groq_stream(LEGACY_MESSAGES))

    _always_raise(monkeypatch, requests.exceptions.ConnectionError("boom"))
    with pytest.raises(Exception) as new_exc:
        list(_new_provider().stream(NEW_MESSAGES))

    assert str(legacy_exc.value) == str(new_exc.value)
