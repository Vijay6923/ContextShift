"""
Summarization as a context-management operation.

Compresses a list of messages into a dense summary via an LLM provider
(contextshift.llm). Kept as its own subpackage rather than folded into
strategies/ because summarization is both a standalone operation (the
original application's manual "Summarize" action) and a building block
future strategies may call into.
"""
