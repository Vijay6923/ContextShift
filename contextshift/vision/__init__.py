"""
Vision (image understanding) capability.

Defines a common interface (VisionProvider) for describing an image via
a vision-capable model, plus a concrete provider -- currently
GeminiVisionProvider. Structurally separate from contextshift.llm: a
vision call takes a single image and a prompt, not a Message history,
and its request shape, model, and defaults all differ from a chat
completion -- see docs/decisions/0010-multimodal-architecture-review.md
for the full reasoning behind the split.

Does not preprocess images itself -- see contextshift.ingestion for
that (docs/decisions/0008-ingestion-vs-ai-boundary.md).
"""
from contextshift.vision.base import VisionProvider
from contextshift.vision.gemini import GeminiVisionProvider

__all__ = ["VisionProvider", "GeminiVisionProvider"]
