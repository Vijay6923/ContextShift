"""
Unit tests for utils.file_processor.analyze_image_with_gemini. The
Gemini client is mocked throughout -- no network access, no real API key
needed. A byte-identical comparison of the preprocessing step against
contextshift.ingestion.image.prepare_image_for_vision lives in
test_ingestion_characterization.py.
"""
import io

import pytest
from google.genai import errors

from config import Config
from utils import file_processor


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
    fake_models = _FakeModels(**kwargs)

    class _FakeClient:
        def __init__(self, *args, **kw):
            self.models = fake_models

    monkeypatch.setattr(file_processor.genai, "Client", _FakeClient)
    return fake_models


def _small_png():
    from PIL import Image

    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_requires_gemini_api_key(monkeypatch):
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        file_processor.analyze_image_with_gemini(_small_png(), "image/png")


def test_returns_response_text(monkeypatch):
    _install_fake_client(monkeypatch, response_text="An image of a cat.")

    result = file_processor.analyze_image_with_gemini(_small_png(), "image/png", "describe")

    assert result == "An image of a cat."


def test_uses_default_prompt_when_user_prompt_empty(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    file_processor.analyze_image_with_gemini(_small_png(), "image/png", user_prompt="")

    sent_prompt = fake_models.calls[0]["contents"][1]
    assert "analyze this image in detail" in sent_prompt


def test_uses_custom_prompt_when_provided(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    file_processor.analyze_image_with_gemini(_small_png(), "image/png", user_prompt="What color is this?")

    sent_prompt = fake_models.calls[0]["contents"][1]
    assert sent_prompt == "What color is this?"


def test_uses_configured_gemini_model(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)

    file_processor.analyze_image_with_gemini(_small_png(), "image/png")

    assert fake_models.calls[0]["model"] == Config.GEMINI_MODEL


def test_sends_image_bytes_directly_not_base64(monkeypatch):
    fake_models = _install_fake_client(monkeypatch)
    original = _small_png()

    file_processor.analyze_image_with_gemini(original, "image/png")

    image_part = fake_models.calls[0]["contents"][0]
    # Preprocessing re-encodes as JPEG, but the key point is: raw bytes,
    # not a base64 string, are what the SDK receives.
    assert isinstance(image_part.inline_data.data, bytes)
    assert image_part.inline_data.mime_type == "image/jpeg"


def test_rate_limit_error_gives_friendly_message(monkeypatch):
    exc = errors.APIError(code=429, response_json={"error": {"message": "rate limited"}})
    _install_fake_client(monkeypatch, exc=exc)

    with pytest.raises(Exception, match="rate limit"):
        file_processor.analyze_image_with_gemini(_small_png(), "image/png")


def test_other_api_error_is_wrapped_with_clear_message(monkeypatch):
    exc = errors.APIError(code=500, response_json={"error": {"message": "server error"}})
    _install_fake_client(monkeypatch, exc=exc)

    with pytest.raises(Exception, match="Failed to analyze image with Gemini"):
        file_processor.analyze_image_with_gemini(_small_png(), "image/png")


def test_unexpected_error_is_wrapped(monkeypatch):
    _install_fake_client(monkeypatch, exc=ConnectionError("boom"))

    with pytest.raises(Exception, match="Failed to analyze image with Gemini"):
        file_processor.analyze_image_with_gemini(_small_png(), "image/png")


def test_empty_response_text_raises(monkeypatch):
    _install_fake_client(monkeypatch, response_text="")

    with pytest.raises(Exception, match="empty response"):
        file_processor.analyze_image_with_gemini(_small_png(), "image/png")
