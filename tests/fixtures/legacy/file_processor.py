import io


# --- PDF Extraction ---

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file using PyPDF2."""
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
