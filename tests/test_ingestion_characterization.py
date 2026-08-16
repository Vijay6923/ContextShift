"""
Direct comparison between legacy utils.file_processor.extract_text_from_pdf
and the new contextshift.ingestion.pdf.extract_text_from_pdf, proving PDF
extraction is unchanged despite being ported (Step 7,
docs/decisions/0008-ingestion-vs-ai-boundary.md).

Image preprocessing (contextshift.ingestion.image.prepare_image_for_vision)
was originally characterized here too, against legacy's combined
analyze_image_with_gemini (preprocessing + an AI call in one function).
That function no longer exists -- it was replaced by
contextshift.vision.GeminiVisionProvider (Vision capability), which
itself proves it delegates to prepare_image_for_vision rather than
reimplementing preprocessing; see
test_routes_preprocessing_through_ingestion_not_reimplemented in
tests/test_gemini_vision_provider.py.
"""
import pytest

from contextshift.ingestion.pdf import extract_text_from_pdf
from tests.fixtures.legacy import file_processor as legacy


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
