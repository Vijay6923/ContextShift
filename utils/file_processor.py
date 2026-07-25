import base64
import io
import requests
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


# --- Image Analysis via Groq Vision ---

def analyze_image_with_groq(file_bytes: bytes, mime_type: str, user_prompt: str = "") -> str:
    """Send an image to Groq's vision model and return the response text."""
    if not Config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in environment.")

    # --- Resize & compress image so it fits within Groq's payload limit ---
    try:
        from PIL import Image
        import io as _io

        img = Image.open(_io.BytesIO(file_bytes))

        # Convert palette/RGBA to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Groq recommends max 1568px on the longest side
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

    # Encode image as base64 data URL
    b64_image = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64_image}"

    prompt_text = user_prompt.strip() if user_prompt.strip() else (
        "Please analyze this image in detail. Describe what you see, "
        "extract any text present, and provide any relevant insights."
    )

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                    {
                        "type": "text",
                        "text": prompt_text,
                    },
                ],
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.5,
    }

    _MAX_RETRIES = 3
    _BASE_BACKOFF = 5

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.post(
                Config.GROQ_BASE_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            if response.status_code == 429:
                import time
                retry_after = int(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                print(f"[GROQ VISION] Rate limited (attempt {attempt}/{_MAX_RETRIES}). "
                      f"Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"[GROQ VISION ERROR] attempt {attempt}: {str(e)}")
            if attempt == _MAX_RETRIES:
                if "429" in str(e):
                    raise Exception("Groq rate limit reached. Please wait a moment and try again.")
                raise Exception(f"Failed to analyze image with Groq: {str(e)}")
            import time
            time.sleep(_BASE_BACKOFF * attempt)

    raise Exception("Groq vision API request failed after maximum retries.")

