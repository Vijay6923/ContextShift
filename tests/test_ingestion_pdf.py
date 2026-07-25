"""
Tests for PDF text extraction. PyPDF2 itself is mocked at the boundary --
verifying this function's own logic (page iteration, labeling, joining,
the no-readable-text error path), not PyPDF2's PDF-parsing correctness,
which is PyPDF2's own responsibility and already covered by its own test
suite. A direct comparison against the legacy implementation, using the
same mocking approach, lives in test_ingestion_characterization.py.
"""
import pytest

from contextshift.ingestion.pdf import extract_text_from_pdf


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


def _mock_pdf_reader(monkeypatch, pages):
    import PyPDF2

    fake_reader = _FakeReader(pages)
    monkeypatch.setattr(PyPDF2, "PdfReader", lambda _bytes_io: fake_reader)


def test_extracts_and_labels_each_page(monkeypatch):
    _mock_pdf_reader(monkeypatch, [_FakePage("First page."), _FakePage("Second page.")])

    result = extract_text_from_pdf(b"fake pdf bytes")

    assert result == "[Page 1]\nFirst page.\n\n[Page 2]\nSecond page."


def test_skips_pages_with_no_readable_text(monkeypatch):
    _mock_pdf_reader(
        monkeypatch,
        [_FakePage("Real content."), _FakePage(""), _FakePage(None), _FakePage("   ")],
    )

    result = extract_text_from_pdf(b"fake pdf bytes")

    assert result == "[Page 1]\nReal content."


def test_strips_whitespace_around_page_text(monkeypatch):
    _mock_pdf_reader(monkeypatch, [_FakePage("  padded text  \n")])

    result = extract_text_from_pdf(b"fake pdf bytes")

    assert result == "[Page 1]\npadded text"


def test_raises_when_no_page_has_readable_text(monkeypatch):
    _mock_pdf_reader(monkeypatch, [_FakePage(""), _FakePage(None)])

    with pytest.raises(Exception, match="No readable text found"):
        extract_text_from_pdf(b"fake pdf bytes")
