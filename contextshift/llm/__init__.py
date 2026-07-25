"""
LLM provider abstraction.

Defines a common interface for completing and streaming chat requests,
plus one or more concrete providers (starting with Groq, carried over
from the original application's direct REST calls). Strategies that need
to call an LLM (e.g. summarization) depend on this interface rather than
on any specific vendor's API, so the provider can be swapped without
touching strategy code.
"""
