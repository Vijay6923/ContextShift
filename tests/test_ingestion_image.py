"""
Tests for image preprocessing. Uses real Pillow-generated test images
(cheap and dependency-free) rather than mocking -- unlike PDF parsing,
there's no friction to exercising the real library here. A proof that
contextshift.vision.GeminiVisionProvider actually delegates to this
module rather than reimplementing preprocessing lives in
test_gemini_vision_provider.py.
"""
import io

from PIL import Image

from contextshift.ingestion.image import JPEG_QUALITY, MAX_DIMENSION_PX, prepare_image_for_vision


def _make_image_bytes(width, height, mode="RGB", fmt="PNG"):
    img = Image.new(mode, (width, height))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_small_image_is_converted_to_jpeg_unchanged_in_size():
    original = _make_image_bytes(100, 80, mode="RGB", fmt="PNG")

    processed_bytes, processed_mime = prepare_image_for_vision(original, "image/png")

    assert processed_mime == "image/jpeg"
    result_img = Image.open(io.BytesIO(processed_bytes))
    assert result_img.format == "JPEG"
    assert result_img.size == (100, 80)


def test_oversized_image_is_thumbnailed_to_max_dimension():
    original = _make_image_bytes(MAX_DIMENSION_PX + 500, 200, mode="RGB", fmt="PNG")

    processed_bytes, _ = prepare_image_for_vision(original, "image/png")

    result_img = Image.open(io.BytesIO(processed_bytes))
    assert max(result_img.size) <= MAX_DIMENSION_PX
    # Aspect ratio preserved by thumbnail().
    assert result_img.size[0] > result_img.size[1]


def test_image_within_bounds_is_not_resized():
    original = _make_image_bytes(500, 300, mode="RGB", fmt="PNG")

    processed_bytes, _ = prepare_image_for_vision(original, "image/png")

    result_img = Image.open(io.BytesIO(processed_bytes))
    assert result_img.size == (500, 300)


def test_rgba_image_is_converted_to_rgb_before_jpeg_encoding():
    original = _make_image_bytes(50, 50, mode="RGBA", fmt="PNG")

    processed_bytes, _ = prepare_image_for_vision(original, "image/png")

    result_img = Image.open(io.BytesIO(processed_bytes))
    assert result_img.mode == "RGB"


def test_falls_back_to_original_bytes_and_mime_on_invalid_image_data(capsys):
    garbage = b"this is not an image"

    processed_bytes, processed_mime = prepare_image_for_vision(garbage, "image/png")

    assert processed_bytes == garbage
    assert processed_mime == "image/png"
    assert "[IMAGE RESIZE] Warning" in capsys.readouterr().out


def test_constants_match_legacy_values():
    assert MAX_DIMENSION_PX == 1568
    assert JPEG_QUALITY == 85
