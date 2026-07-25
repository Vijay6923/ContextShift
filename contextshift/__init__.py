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
"""

__version__ = "0.1.0"
