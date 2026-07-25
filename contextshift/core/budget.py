"""Immutable token-budget configuration for context-management strategies."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """
    An immutable description of how much context a strategy may use.

    Strategies receive a TokenBudget; they do not modify it. This mirrors
    how the equivalent configuration is actually used today -- a fixed
    ceiling a strategy prunes down to -- and rules out an entire class of
    bug where adjustments made during one strategy call leak into the
    next call's budget.

    Invariants (enforced at construction):
        - `max_tokens` must be positive.
        - `safety_margin` must be non-negative and no larger than
          `max_tokens` -- a margin that consumes the entire budget, or
          more, would leave no room to ever include a message.

    Args:
        max_tokens: The nominal size of the context window being managed,
            in tokens.
        safety_margin: Tokens deliberately held back from `max_tokens`
            (e.g. for the model's own response, or slack for token-count
            estimation error). Strategies should stay under
            `effective_limit`, not `max_tokens`, directly.
    """

    max_tokens: int
    safety_margin: int = 0

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")
        if self.safety_margin < 0:
            raise ValueError(f"safety_margin must be non-negative, got {self.safety_margin}")
        if self.safety_margin > self.max_tokens:
            raise ValueError(
                f"safety_margin ({self.safety_margin}) cannot exceed max_tokens ({self.max_tokens})"
            )

    @property
    def effective_limit(self) -> int:
        """The actual token ceiling a strategy should stay under: max_tokens - safety_margin."""
        return self.max_tokens - self.safety_margin
