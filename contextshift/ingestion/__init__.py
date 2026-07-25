"""
Non-text content ingestion.

Extracts usable text or model-ready bytes from inputs that aren't
already chat messages -- PDF text extraction and image preprocessing,
carried over from the original application's upload handling. Operates
on raw bytes, never on Flask request objects or any application-specific
type, so it is reusable outside a web application (a CLI, a batch
ingestion script, an eval harness fixture).

Deliberately does NOT include AI-based image understanding (calling a
vision model to describe an image). Document/image extraction and
LLM-based understanding are different concerns -- see
docs/decisions/0008-ingestion-vs-ai-boundary.md for the reasoning, and
for where the original application's vision-calling code remains,
unported, as a named gap rather than a premature abstraction.
"""
from contextshift.ingestion.image import prepare_image_for_vision
from contextshift.ingestion.pdf import extract_text_from_pdf

__all__ = ["extract_text_from_pdf", "prepare_image_for_vision"]
