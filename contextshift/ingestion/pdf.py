"""PDF text extraction, ported mechanically from the original application."""
from __future__ import annotations

import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all readable text from a PDF, page by page.

    Ported mechanically from the original application's
    utils/file_processor.py::extract_text_from_pdf: identical PyPDF2
    usage, identical per-page "[Page N]" labeling, identical behavior on
    a PDF with no extractable text (raises, rather than returning an
    empty string -- most likely a scanned/image-only PDF, which this
    function makes no attempt to OCR). The lazy, try/except-guarded
    PyPDF2 import is preserved as-is, even though PyPDF2 is a hard
    requirement of this project (see requirements.txt) and that
    ImportError branch is not currently reachable in practice -- not
    "cleaned up" into a top-level import, per the mechanical-port
    instruction.

    Pure ingestion: no network, no AI, no application-specific types.
    Operates on raw bytes in, text out.

    Args:
        file_bytes: Raw PDF bytes.

    Returns:
        Extracted text, pages joined by a blank line, each prefixed with
        "[Page N]".

    Raises:
        Exception: if PyPDF2 is unavailable, or if no page yielded any
            readable text.
    """
    try:
        import PyPDF2
    except ImportError:
        raise Exception("PyPDF2 is not installed. Run: pip install PyPDF2")

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages_text.append(f"[Page {i + 1}]\n{text.strip()}")

    if not pages_text:
        raise Exception("No readable text found in this PDF. It may be a scanned image PDF.")

    return "\n\n".join(pages_text)
