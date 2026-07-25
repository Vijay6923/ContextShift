"""PDF text extraction."""
from __future__ import annotations

import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all readable text from a PDF, page by page.

    Pure ingestion: no network, no AI, no application-specific types.
    Operates on raw bytes in, text out.

    Raises rather than returning an empty string when no page yields any
    readable text -- most likely a scanned/image-only PDF, which this
    function makes no attempt to OCR.

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
