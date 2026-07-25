"""
ContextShift: a framework for experimenting with LLM context-window
management strategies (sliding window, pinning, summarization, semantic
retrieval, and beyond).

This package has no dependency on Flask, SQLAlchemy, or any other
application-layer framework. It is designed to be usable on its own --
by a CLI, a notebook, an evaluation harness, or a web application -- with
the web application in this repository being just one such consumer.

Currently being extracted incrementally from the original single-file
Flask application; subpackages are scaffolded ahead of the logic that
will populate them.

The top-level package deliberately re-exports nothing. Import types from
their owning subpackage instead (e.g. `from contextshift.core import
Message`) -- see docs/decisions/0002-minimal-public-api-surface.md for
why the public surface is being kept deliberately minimal before 1.0.
"""

__version__ = "0.1.0"
