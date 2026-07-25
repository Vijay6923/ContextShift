"""
Pluggable token-estimation backends.

Defines a common interface for turning message text into a token count,
plus one or more concrete implementations (starting with the heuristic
word-count estimator carried over from the original application).
Strategies depend on this subpackage to measure how much of the token
budget a candidate context consumes; this subpackage depends only on
contextshift.core.
"""
