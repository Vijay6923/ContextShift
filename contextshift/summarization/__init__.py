"""
Summarization as a domain service.

Compresses a list of messages into a dense summary via an LLMProvider
(contextshift.llm) -- the original application's manual "Summarize"
action, extracted as a reusable service that expresses *what* to ask a
model, leaving *how* to talk to that model entirely to the LLMProvider it
depends on. Depends only on the LLMProvider interface, never on a
concrete provider like GroqProvider, so any conforming provider
(including a fake one, for tests) can be substituted with no change here.

Currently a single concrete implementation (Summarizer), not a pluggable
interface with multiple approaches -- see
docs/decisions/0007-summarizer-domain-service.md for why introducing a
Protocol was deliberately deferred, the same way a strategy registry was
deferred in Step 4 until a second strategy existed to make one meaningful.
"""
from contextshift.summarization.summarizer import DEFAULT_MAX_TOKENS, Summarizer

__all__ = ["Summarizer", "DEFAULT_MAX_TOKENS"]
