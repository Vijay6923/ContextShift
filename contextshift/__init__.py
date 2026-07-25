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
    strategies      ContextStrategy protocol + PinnedRecencyStrategy
    llm             LLMProvider protocol + GroqProvider
    summarization   Summarizer, built on LLMProvider
    ingestion       PDF text extraction, image preprocessing

The top-level package deliberately re-exports nothing. Import types from
their owning subpackage instead (e.g. `from contextshift.core import
Message`) -- see docs/decisions/0002-minimal-public-api-surface.md for
why the public surface is kept deliberately minimal pre-1.0.
"""

__version__ = "0.1.0"
