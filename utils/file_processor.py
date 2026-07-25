import io

from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import Config


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


# --- Image Analysis via Google Gemini ---

_MAX_RETRIES = 3
_INITIAL_RETRY_DELAY_SECONDS = 5
_TIMEOUT_MS = 60_000  # 60s


def analyze_image_with_gemini(file_bytes: bytes, mime_type: str, user_prompt: str = "") -> str:
    """Send an image to Google Gemini (see Config.GEMINI_MODEL) and return the response text."""
    if not Config.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in environment.")

    # --- Resize & compress image so it fits comfortably within the model's payload limits ---
    try:
        from PIL import Image
        import io as _io

        img = Image.open(_io.BytesIO(file_bytes))

        # Convert palette/RGBA to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Keep the longest side within a reasonable bound for vision models
        MAX_DIM = 1568
        if max(img.width, img.height) > MAX_DIM:
            img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)

        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        file_bytes = buf.getvalue()
        mime_type = "image/jpeg"

    except Exception as resize_err:
        # If Pillow fails for some reason, proceed with original bytes
        print(f"[IMAGE RESIZE] Warning: {resize_err}")

    prompt_text = user_prompt.strip() if user_prompt.strip() else (
        "Please analyze this image in detail. Describe what you see, "
        "extract any text present, and provide any relevant insights."
    )

    # The SDK accepts raw bytes directly (types.Part.from_bytes) -- no
    # manual base64 encoding needed; that's an implementation detail the
    # SDK/API handles internally for transport.
    client = genai.Client(
        api_key=Config.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(
                attempts=_MAX_RETRIES,
                initial_delay=_INITIAL_RETRY_DELAY_SECONDS,
                exp_base=2.0,
                http_status_codes=[429, 500, 502, 503, 504],
            ),
        ),
    )

    try:
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                prompt_text,
            ],
            config=types.GenerateContentConfig(max_output_tokens=1024, temperature=0.5),
        )
    except APIError as e:
        print(f"[GEMINI VISION ERROR] {e.code}: {e}")
        if e.code == 429:
            raise Exception("Gemini rate limit reached. Please wait a moment and try again.")
        raise Exception(f"Failed to analyze image with Gemini: {e}")
    except Exception as e:
        print(f"[GEMINI VISION ERROR] {e}")
        raise Exception(f"Failed to analyze image with Gemini: {e}")

    if not response.text:
        raise Exception("Gemini returned an empty response.")

    return response.text
