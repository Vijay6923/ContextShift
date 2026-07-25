"""
Direct comparison between legacy utils.file_processor (still what the
running application uses) and the new contextshift.ingestion, proving
the extraction/preprocessing logic is unchanged despite being ported --
and, for images, split (see docs/decisions/0008-ingestion-vs-ai-boundary.md).

The image comparison is the more interesting proof: legacy's
analyze_image_with_gemini does preprocessing *and* an AI call in one
function, with no way to observe the preprocessed bytes directly. So
this captures what legacy actually hands to the Gemini SDK (with the
client mocked) and asserts it's byte-identical to
contextshift.ingestion.image.prepare_image_for_vision's output for the
same input -- proving the split introduced no drift, not just asserting
it didn't.
"""
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
    captured = {}

    class _FakeGeminiResponse:
        text = "A description."

    class _FakeGeminiModels:
        def generate_content(self, *, model, contents, config=None):
            captured["contents"] = contents
            return _FakeGeminiResponse()

    class _FakeGeminiClient:
        def __init__(self, *args, **kwargs):
            self.models = _FakeGeminiModels()

    monkeypatch.setattr("utils.file_processor.genai.Client", _FakeGeminiClient)
    legacy.analyze_image_with_gemini(file_bytes, mime_type, "describe this")

    image_part = captured["contents"][0]
    return image_part.inline_data.data, image_part.inline_data.mime_type


def test_preprocessing_matches_what_legacy_actually_sends_to_gemini(monkeypatch):
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
