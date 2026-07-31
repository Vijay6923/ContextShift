"""Behavioral contract every vision provider satisfies."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VisionProvider(Protocol):
    """
    Anything that can turn an image into a model-generated text
    description.

    A structural Protocol, not an ABC, per
    docs/decisions/0005-protocol-over-abc.md. Deliberately
    capability-oriented rather than vendor-oriented: nothing in this
    interface mentions Gemini or any specific wire format. A conforming
    implementation owns everything about *how* it talks to a vision
    model -- authentication, SDK/HTTP transport, retries, request
    payload shape -- none of which is visible here. See
    contextshift.vision.gemini.GeminiVisionProvider for the first
    implementation, and
    docs/decisions/0010-multimodal-architecture-review.md for why this
    is a separate interface from LLMProvider rather than an extension
    of it.

    Deliberately narrower than LLMProvider: no conversation history (a
    vision call is a single image plus a single prompt, not a chat
    turn, per ADR 0010 Section 1), and no streaming variant (no
    consumer of this capability, past or present, has ever needed one).

    Does not own image preprocessing -- a conforming implementation is
    expected to prepare raw bytes itself (e.g. via
    contextshift.ingestion.prepare_image_for_vision) before sending
    anything to a model. See
    docs/decisions/0008-ingestion-vs-ai-boundary.md.
    """

    def describe(self, image_bytes: bytes, mime_type: str, prompt: str | None = None) -> str:
        """
        Return a model-generated description of an image.

        `prompt` is optional: `None` (the default) requests the
        provider's own general-description behavior; a caller-supplied
        prompt replaces that default entirely, guiding what the model
        looks for instead.
        """
        ...
