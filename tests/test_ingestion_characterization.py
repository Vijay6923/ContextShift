"""
Direct comparison between legacy utils.file_processor (still what the
running application uses) and the new contextshift.ingestion, proving
the extraction/preprocessing logic is unchanged despite being ported --
and, for images, split (see docs/decisions/0008-ingestion-vs-ai-boundary.md).

The image comparison is the more interesting proof: legacy's
analyze_image_with_groq does preprocessing *and* an AI call in one
function, with no way to observe the preprocessed bytes directly. So
this captures what legacy actually embeds in the base64 payload it sends
to Groq (with the network call mocked) and asserts it's byte-identical
to contextshift.ingestion.image.prepare_image_for_vision's output for
the same input -- proving the split introduced no drift, not just
asserting it didn't.
"""
import base64
import io

import pytest

from contextshift.ingestion.image import prepare_image_for_vision
from contextshift.ingestion.pdf import extract_text_from_pdf
from utils import file_processor as legacy


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        pass


# -- PDF --------------------------------------------------------------------


def test_pdf_extraction_matches_legacy(monkeypatch):
    import PyPDF2

    fake_reader = _FakeReader([_FakePage("Page one text."), _FakePage("Page two text.")])
    monkeypatch.setattr(PyPDF2, "PdfReader", lambda _bytes_io: fake_reader)

    legacy_result = legacy.extract_text_from_pdf(b"fake pdf bytes")
    new_result = extract_text_from_pdf(b"fake pdf bytes")

    assert legacy_result == new_result == "[Page 1]\nPage one text.\n\n[Page 2]\nPage two text."


def test_pdf_extraction_raises_identically_on_no_readable_text(monkeypatch):
    import PyPDF2

    fake_reader = _FakeReader([_FakePage(""), _FakePage(None)])
    monkeypatch.setattr(PyPDF2, "PdfReader", lambda _bytes_io: fake_reader)

    with pytest.raises(Exception) as legacy_exc:
        legacy.extract_text_from_pdf(b"fake pdf bytes")
    with pytest.raises(Exception) as new_exc:
        extract_text_from_pdf(b"fake pdf bytes")

    assert str(legacy_exc.value) == str(new_exc.value)


# -- Image preprocessing (extracted from a combined legacy function) --------


def _make_image_bytes(width, height, mode="RGB", fmt="PNG"):
    from PIL import Image

    img = Image.new(mode, (width, height))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _capture_legacy_vision_payload(monkeypatch, file_bytes, mime_type):
    import requests

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse(200, {"choices": [{"message": {"content": "A description."}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    legacy.analyze_image_with_groq(file_bytes, mime_type, "describe this")

    data_url = captured["payload"]["messages"][0]["content"][0]["image_url"]["url"]
    header, b64_data = data_url.split(",", 1)
    sent_bytes = base64.b64decode(b64_data)
    sent_mime = header.split(";")[0].replace("data:", "")
    return sent_bytes, sent_mime


def test_preprocessing_matches_what_legacy_actually_sends_to_groq(monkeypatch):
    original_bytes = _make_image_bytes(2000, 500, mode="RGBA", fmt="PNG")

    legacy_sent_bytes, legacy_sent_mime = _capture_legacy_vision_payload(monkeypatch, original_bytes, "image/png")
    new_bytes, new_mime = prepare_image_for_vision(original_bytes, "image/png")

    assert legacy_sent_mime == new_mime == "image/jpeg"
    assert legacy_sent_bytes == new_bytes


def test_preprocessing_matches_legacy_for_small_image_needing_no_resize(monkeypatch):
    original_bytes = _make_image_bytes(200, 150, mode="RGB", fmt="PNG")

    legacy_sent_bytes, legacy_sent_mime = _capture_legacy_vision_payload(monkeypatch, original_bytes, "image/png")
    new_bytes, new_mime = prepare_image_for_vision(original_bytes, "image/png")

    assert legacy_sent_mime == new_mime == "image/jpeg"
    assert legacy_sent_bytes == new_bytes


def test_preprocessing_fallback_matches_legacy_on_invalid_image_data(monkeypatch):
    garbage = b"not an image at all"

    legacy_sent_bytes, legacy_sent_mime = _capture_legacy_vision_payload(monkeypatch, garbage, "image/png")
    new_bytes, new_mime = prepare_image_for_vision(garbage, "image/png")

    # Both fall back to the ORIGINAL bytes/mime unchanged when Pillow can't process the input.
    assert legacy_sent_bytes == garbage == new_bytes
    assert legacy_sent_mime == "image/png" == new_mime
