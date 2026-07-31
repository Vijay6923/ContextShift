"""
Unit tests for GeminiVisionProvider. The Gemini client is mocked
throughout -- no network access, no real API key needed.

Ported from tests/test_gemini_vision.py, which tested
utils.file_processor.analyze_image_with_gemini before that function was
deleted in favor of this provider (Vision capability). Each assertion
here is a behavioral data point already proven true of the function
this class replaced -- see the old test file's git history for the
side-by-side reference, and
docs/decisions/0008-ingestion-vs-ai-boundary.md /
docs/decisions/0010-multimodal-architecture-review.md for why the split
happened. One behavior intentionally changed, not preserved: API-key
validation moved from call time to construction time, matching
contextshift.llm.GroqProvider's established pattern (see
test_requires_api_key_at_construction below).
"""
import io

import pytest
from google.genai import errors

from contextshift.vision.gemini import GeminiVisionProvider


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, response_text="A description.", exc=None):
        self._response_text = response_text
        self._exc = exc
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._response_text)


def _install_fake_client(monkeypatch, **kwargs):
    import contextshift.vision.gemini as gemini_module

    fake_models = _FakeModels(**kwargs)

    class _FakeClient:
        def __init__(self, *args, **kw):
            self.models = fake_models

    monkeypatch.setattr(gemini_module.genai, "Client", _FakeClient)
    return fake_models


def _small_png():
    from PIL import Image

    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_requires_api_key_at_construction():
    with pytest.raises(ValueError, match="api_key is required"):
        GeminiVisionProvider(api_key="")


def test_returns_response_text(monkeypatch):
    _install_fake_client(monkeypatch, response_text="An image of a cat.")

    result = GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png", "describe")

    assert result == "An image of a cat."


def test_uses_default_prompt_when_prompt_is_none(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png", prompt=None)

    sent_prompt = fake_models.calls[0]["contents"][1]
    assert "analyze this image in detail" in sent_prompt


def test_uses_default_prompt_when_prompt_is_blank(monkeypatch):
    # Matches legacy: a whitespace-only prompt is treated the same as
    # no prompt at all, not sent to the model verbatim.
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png", prompt="   ")

    sent_prompt = fake_models.calls[0]["contents"][1]
    assert "analyze this image in detail" in sent_prompt


def test_uses_custom_prompt_when_provided(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png", prompt="What color is this?")

    sent_prompt = fake_models.calls[0]["contents"][1]
    assert sent_prompt == "What color is this?"


def test_uses_configured_model(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k", model="a-specific-model").describe(_small_png(), "image/png")

    assert fake_models.calls[0]["model"] == "a-specific-model"


def test_sends_image_bytes_directly_not_base64(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png")

    image_part = fake_models.calls[0]["contents"][0]
    # Preprocessing re-encodes as JPEG, but the key point is: raw bytes,
    # not a base64 string, are what the SDK receives.
    assert isinstance(image_part.inline_data.data, bytes)
    assert image_part.inline_data.mime_type == "image/jpeg"


def test_routes_preprocessing_through_ingestion_not_reimplemented(monkeypatch):
    # The provider must not resize/convert/re-encode images itself --
    # that is contextshift.ingestion.prepare_image_for_vision's job
    # (ADR 0008, ADR 0010 Section 2). This proves delegation, not just a
    # matching end result: prepare_image_for_vision's return value, not
    # a locally reimplemented equivalent, is what reaches Gemini.
    import contextshift.vision.gemini as gemini_module

    calls = []

    def _fake_prepare(image_bytes, mime_type):
        calls.append((image_bytes, mime_type))
        return b"processed-bytes", "image/jpeg"

    monkeypatch.setattr(gemini_module, "prepare_image_for_vision", _fake_prepare)
    fake_models = _install_fake_client(monkeypatch)

    GeminiVisionProvider(api_key="k").describe(b"raw-bytes", "image/png")

    assert calls == [(b"raw-bytes", "image/png")]
    image_part = fake_models.calls[0]["contents"][0]
    assert image_part.inline_data.data == b"processed-bytes"
    assert image_part.inline_data.mime_type == "image/jpeg"


def test_rate_limit_error_gives_friendly_message(monkeypatch):
    exc = errors.APIError(code=429, response_json={"error": {"message": "rate limited"}})
    _install_fake_client(monkeypatch, exc=exc)

    with pytest.raises(Exception, match="rate limit"):
        GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png")


def test_other_api_error_is_wrapped_with_clear_message(monkeypatch):
    exc = errors.APIError(code=500, response_json={"error": {"message": "server error"}})
    _install_fake_client(monkeypatch, exc=exc)

    with pytest.raises(Exception, match="Failed to analyze image with Gemini"):
        GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png")


def test_unexpected_error_is_wrapped(monkeypatch):
    _install_fake_client(monkeypatch, exc=ConnectionError("boom"))

    with pytest.raises(Exception, match="Failed to analyze image with Gemini"):
        GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png")


def test_empty_response_text_raises(monkeypatch):
    _install_fake_client(monkeypatch, response_text="")

    with pytest.raises(Exception, match="empty response"):
        GeminiVisionProvider(api_key="k").describe(_small_png(), "image/png")
