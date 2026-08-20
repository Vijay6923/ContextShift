"""
LLM provider abstraction.

Defines a common interface (LLMProvider) for completing and streaming
chat requests, plus concrete providers -- currently GroqProvider and
OpenRouterProvider. Code
that needs to call an LLM (contextshift.summarization, for instance)
depends on this interface rather than on any specific vendor's API, so
the provider can be swapped without touching the code that uses it.

Not every part of ContextShift needs this subpackage: contextshift.core,
contextshift.tokenizers, and contextshift.strategies have no dependency
on it and are not expected to gain one -- PinnedRecencyStrategy, for
instance, never calls an LLM at all. See docs/architecture.md's
dependency rules for the actual, current dependency graph.
"""
from contextshift.llm.base import LLMProvider
from contextshift.llm.groq import GroqProvider
from contextshift.llm.openrouter import OpenRouterProvider

__all__ = ["LLMProvider", "GroqProvider", "OpenRouterProvider"]
