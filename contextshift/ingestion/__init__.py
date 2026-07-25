"""
Non-text content ingestion.

Extracts text/analysis from files that aren't already chat messages --
PDF text extraction and image analysis via vision models, carried over
from the original application's upload handling. Operates on raw bytes,
not web-framework request objects, so it is reusable outside a web
application (e.g. a batch ingestion script).
"""
