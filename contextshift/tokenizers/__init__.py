"""
Pluggable token-estimation backends.

Defines a common interface for approximating the token count of a piece
of text, plus one or more concrete implementations (starting with the
heuristic word-count estimator carried over from the original
application). A Tokenizer answers exactly one question -- "how many
tokens does this text cost?" -- and knows nothing about messages,
strategies, context budgets, or how its result will be used; those are
the concerns of whatever calls it. This subpackage has no dependency on
any other contextshift subpackage, including core -- it operates on
plain strings, not on Message.
"""
from contextshift.tokenizers.base import Tokenizer
from contextshift.tokenizers.heuristic import HeuristicTokenizer

__all__ = ["Tokenizer", "HeuristicTokenizer"]
