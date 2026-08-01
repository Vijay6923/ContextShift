"""
ContextShift: a framework for context engineering -- pluggable
strategies for deciding what an LLM sees, summarization as a domain
service, and a vendor-neutral LLM provider abstraction.

This package has no dependency on Flask, SQLAlchemy, or any other
application-layer framework. It is designed to be usable on its own --
by a CLI, a notebook, an evaluation harness, or a web application. The
Flask chat application in this repository is one example consumer, not
a special one.

Subpackages:
    core            Message, TokenBudget -- plain domain types
    tokenizers      Tokenizer protocol + HeuristicTokenizer
    strategies      ContextStrategy protocol + PinnedRecencyStrategy,
                    RecencyStrategy, SlidingWindowStrategy
    llm             LLMProvider protocol + GroqProvider
    summarization   Summarizer, built on LLMProvider
    ingestion       PDF text extraction, image preprocessing
    vision          VisionProvider protocol + GeminiVisionProvider
    manager         ContextManager -- orchestrates a strategy and a
                    provider into a chat turn
    testing         FakeLLMProvider -- an in-memory LLMProvider for
                    building against this library with no network calls
    benchmark       Deterministic ContextStrategy comparison -- messages
                    kept/discarded, tokens kept/discarded, latency

The top-level package re-exports exactly one name: ContextManager.
Everything else is imported from its owning subpackage (e.g. `from
contextshift.core import Message`) -- see
docs/decisions/0002-minimal-public-api-surface.md for why the public
surface is otherwise kept deliberately minimal, and
docs/decisions/0011-framework-v2-design-review.md (Section 2) for why
ContextManager specifically is the one deliberate exception: it's the
framework's primary orchestration entry point, not a type someone is
expected to reach for by digging into a subpackage first.
"""
from contextshift.manager import ContextManager

__version__ = "0.1.0"

__all__ = ["ContextManager", "__version__"]
