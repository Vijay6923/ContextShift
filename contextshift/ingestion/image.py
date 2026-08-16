"""Image preprocessing for vision models."""
from __future__ import annotations

import io

MAX_DIMENSION_PX = 1568
JPEG_QUALITY = 85


def prepare_image_for_vision(file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """
    Resize, normalize, and re-encode image bytes for a vision model.

    This is "image preparation" -- a pure ingestion concern, deliberately
    separate from calling a vision model to interpret the image. See
    docs/decisions/0008-ingestion-vs-ai-boundary.md for why image
    understanding is not part of this subpackage.

    Resilient by design: if preprocessing fails for *any* reason --
    including Pillow being unavailable at all, which is why the
    `from PIL import Image` import below is local to this function rather
    than at module level -- the original bytes and mime_type are returned
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

        img: Image.Image = Image.open(io.BytesIO(file_bytes))

        # Convert palette/RGBA to RGB for JPEG compatibility.
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        if max(img.width, img.height) > MAX_DIMENSION_PX:
            # Image.Resampling (the enum namespace) was added in Pillow
            # 9.1 -- pyproject.toml's Pillow>=9.1 floor exists specifically
            # to guarantee this attribute exists. Do not lower that floor
            # without also changing this line back to the older top-level
            # Image.LANCZOS constant, or this raises AttributeError on
            # every oversized image, silently caught below.
            img.thumbnail((MAX_DIMENSION_PX, MAX_DIMENSION_PX), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue(), "image/jpeg"

    except Exception as resize_err:
        print(f"[IMAGE RESIZE] Warning: {resize_err}")
        return file_bytes, mime_type
