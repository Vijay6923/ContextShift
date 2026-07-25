"""Image preprocessing for vision models, extracted from the original application."""
from __future__ import annotations

import io

MAX_DIMENSION_PX = 1568
JPEG_QUALITY = 85


def prepare_image_for_vision(file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """
    Resize, normalize, and re-encode image bytes for a vision model.

    Mechanically extracted from the preprocessing half of the original
    application's analyze_image_with_groq
    (utils/file_processor.py) -- the half that has nothing to do with
    calling a model. This function is the "image preparation" that
    docs/decisions/0008-ingestion-vs-ai-boundary.md identifies as a pure
    ingestion concern; the other half of that legacy function (base64
    encoding a payload, calling Groq's vision endpoint, retrying on
    429) is deliberately NOT here -- see that ADR for where it remains
    and why.

    Ported with the same constants (MAX_DIMENSION_PX, JPEG_QUALITY) and
    the same resilience characteristic: if preprocessing fails for *any*
    reason -- including Pillow being unavailable at all, which is why
    the `from PIL import Image` import below is deliberately local to
    this function rather than at module level, exactly mirroring
    legacy's structure -- the original bytes and mime_type are returned
    unchanged, with a warning printed, rather than raising.

    Pure ingestion: no network, no AI, no application-specific types.
    Operates on raw bytes in, processed bytes out.

    Args:
        file_bytes: Raw image bytes.
        mime_type: The image's reported MIME type.

    Returns:
        (processed_bytes, processed_mime_type). On success, always
        (JPEG-encoded bytes, "image/jpeg"). On any failure, the original
        (file_bytes, mime_type), unchanged.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(file_bytes))

        # Convert palette/RGBA to RGB for JPEG compatibility.
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        if max(img.width, img.height) > MAX_DIMENSION_PX:
            img.thumbnail((MAX_DIMENSION_PX, MAX_DIMENSION_PX), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue(), "image/jpeg"

    except Exception as resize_err:
        print(f"[IMAGE RESIZE] Warning: {resize_err}")
        return file_bytes, mime_type
