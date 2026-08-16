"""
Pluggable token-estimation backends.

Defines a common interface for approximating the token count of a
piece of text, plus concrete implementations:

- `HeuristicTokenizer` -- zero-dependency word-count approximation,
  the default. Fast, always available, and measurably inexact -- see
  docs/decisions/0014-accurate-tokenizers.md for its actual error rate
  against a real tokenizer, published rather than left implied.
  Constructing it warns once per process
  (`HeuristicTokenizerAccuracyWarning`) -- see
  docs/decisions/0017-heuristic-tokenizer-safety-default.md.
- `TiktokenTokenizer` -- a real byte-pair-encoding tokenizer via the
  optional `tiktoken` dependency (`pip install contextshift[tiktoken]`).
- `AnthropicTokenizer` -- exact counts via Anthropic's own
  token-counting endpoint, via the optional `anthropic` dependency
  (`pip install contextshift[anthropic]`). Unlike the other two, this
  one makes a real network call.

A Tokenizer answers exactly one question -- "how many tokens does this
text cost?" -- and knows nothing about messages, strategies, context
budgets, or how its result will be used; those are the concerns of
whatever calls it. This subpackage has no dependency on any other
contextshift subpackage, including core -- it operates on plain
strings, not on Message.

Importing `TiktokenTokenizer` or `AnthropicTokenizer` never requires
their optional package to be installed -- only constructing an
instance does, with a clear error naming the install command if it's
missing.
"""
from contextshift.tokenizers.anthropic_native import AnthropicTokenizer
from contextshift.tokenizers.base import Tokenizer
from contextshift.tokenizers.heuristic import HeuristicTokenizer, HeuristicTokenizerAccuracyWarning
from contextshift.tokenizers.tiktoken_backed import TiktokenTokenizer

__all__ = [
    "Tokenizer",
    "HeuristicTokenizer",
    "HeuristicTokenizerAccuracyWarning",
    "TiktokenTokenizer",
    "AnthropicTokenizer",
]
