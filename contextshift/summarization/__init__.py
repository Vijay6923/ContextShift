"""
Summarization as a domain service.

Compresses a list of messages into a dense summary via an LLMProvider
(contextshift.llm) -- a reusable service that expresses *what* to ask a
model, leaving *how* to talk to that model entirely to the LLMProvider it
depends on. Depends only on the LLMProvider interface, never on a
concrete provider like GroqProvider, so any conforming provider
(including a fake one, for tests) can be substituted with no change here.

Currently a single concrete implementation (Summarizer), not a pluggable
interface with multiple approaches -- see
docs/decisions/0007-summarizer-domain-service.md for why introducing a
Protocol here was deliberately deferred until a second summarization
approach exists to design one against.
"""
from contextshift.summarization.summarizer import DEFAULT_MAX_TOKENS, Summarizer

__all__ = ["Summarizer", "DEFAULT_MAX_TOKENS"]
