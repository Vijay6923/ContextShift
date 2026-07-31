"""Google Gemini vision client."""
from __future__ import annotations

from google import genai
from google.genai import types
from google.genai.errors import APIError

from contextshift.ingestion import prepare_image_for_vision

DEFAULT_MODEL = "gemini-flash-latest"

_DEFAULT_PROMPT = (
    "Please analyze this image in detail. Describe what you see, "
    "extract any text present, and provide any relevant insights."
)
_MAX_OUTPUT_TOKENS = 1024
_TEMPERATURE = 0.5
_MAX_RETRIES = 3
_INITIAL_RETRY_DELAY_SECONDS = 5
_TIMEOUT_MS = 60_000  # 60s


class GeminiVisionProvider:
    """
    A VisionProvider (contextshift.vision.base.VisionProvider) backed by
    Google's Gemini API.

    Owns everything Gemini-specific: authentication, SDK client
    construction, retry/backoff configuration, the exact request payload
    shape, and how API errors are mapped to human-readable exceptions.
    None of this is visible through the VisionProvider interface -- code
    holding a VisionProvider has no way to tell it's talking to Gemini
    at all.

    Does not preprocess images itself -- every call routes raw bytes
    through contextshift.ingestion.prepare_image_for_vision() first,
    the same boundary contextshift.llm.GroqProvider draws for transport
    versus contextshift.strategies for message selection. See
    docs/decisions/0008-ingestion-vs-ai-boundary.md and
    docs/decisions/0010-multimodal-architecture-review.md.

    Args:
        api_key: Gemini API key. Required, and validated at construction
            time -- matching contextshift.llm.GroqProvider's pattern, not
            legacy's (which validated at call time). Not read from any
            global configuration -- contextshift never imports
            application configuration directly (see
            docs/decisions/0001-library-independence-and-adapter-placement.md).
            Whatever constructs a GeminiVisionProvider (a Flask adapter,
            a CLI, a notebook) supplies it explicitly.
        model: Gemini model identifier. Defaults to `gemini-flash-latest`.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model

    def describe(self, image_bytes: bytes, mime_type: str, prompt: str | None = None) -> str:
        """
        Return a model-generated description of an image.

        `prompt` is optional: `None` (or an empty/whitespace-only
        string) requests a general description; a caller-supplied
        prompt replaces that default entirely.

        Preprocesses `image_bytes` via
        contextshift.ingestion.prepare_image_for_vision() before sending
        anything to Gemini -- this method never resizes, converts, or
        re-encodes an image itself.
        """
        processed_bytes, processed_mime_type = prepare_image_for_vision(image_bytes, mime_type)
        prompt_text = prompt.strip() if prompt and prompt.strip() else _DEFAULT_PROMPT

        client = genai.Client(
            api_key=self._api_key,
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
                model=self._model,
                contents=[
                    types.Part.from_bytes(data=processed_bytes, mime_type=processed_mime_type),
                    prompt_text,
                ],
                config=types.GenerateContentConfig(
                    max_output_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=_TEMPERATURE,
                ),
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
