"""Summarization-based context-selection strategy."""
from __future__ import annotations

from collections.abc import Sequence

from contextshift.core import Message, TokenBudget
from contextshift.strategies.base import ContextResult, total_tokens
from contextshift.summarization import Summarizer
from contextshift.tokenizers.base import Tokenizer

DEFAULT_KEEP_RECENT = 6


class SummarizationStrategy:
    """
    A ContextStrategy that keeps the most recent `keep_recent`
    messages verbatim and compresses everything older into a single
    summary message, via a Summarizer -- the only strategy in this
    package that discards information by compression instead of by
    dropping it outright.

    This is a genuinely different kind of strategy from the other
    three, in ways worth being explicit about rather than glossing
    over:

    - **It costs a model call.** `PinnedRecencyStrategy`,
      `RecencyStrategy`, and `SlidingWindowStrategy` are pure
      computation; `build()` here calls `self._summarizer.summarize()`,
      which calls an `LLMProvider`. Selection latency, measured by
      `contextshift.benchmark`, means something different for this
      strategy than for the other three -- it now reflects real
      network time, not just list slicing.
    - **It is not deterministic**, unless the `Summarizer` it's given
      is. `contextshift.testing.FakeSummarizer` exists specifically so
      `contextshift.benchmark.needle`'s deterministic tier can still
      run this strategy in CI -- see
      docs/decisions/0015-summarization-strategy.md for the full
      reasoning.
    - **The summary itself consumes budget.** It's measured with the
      same `tokenizer` this strategy is constructed with, and counted
      toward the same `budget` every other strategy respects.
    - **`ContextResult.excluded` means something subtly different
      here.** For the other three strategies, an excluded message is
      genuinely gone. Here, an "excluded" older message was compressed
      into the summary, not necessarily lost -- the information may
      still be present, paraphrased, in `messages[0]`'s content. A
      needle-retention check (which matches by object identity) will
      report a summarized message as *not* retained even if the
      summary preserves the fact it needed -- a known, honest
      limitation of the needle-retention benchmark applied to this
      strategy, not a bug in either.

    Args:
        summarizer: Compresses the older messages into one summary
            string. A real `Summarizer` for production use;
            `contextshift.testing.FakeSummarizer` for deterministic
            tests and benchmarks.
        tokenizer: Measures the token cost of the generated summary,
            so it can be counted against `budget` -- required for the
            same reason `ContextManager` requires one: nothing else
            in this strategy measures the new text it produces.
        keep_recent: How many of the most recent messages are kept
            verbatim, never summarized. Must be at least 1, same
            reasoning as `PinnedRecencyStrategy.recent_buffer` and
            `SlidingWindowStrategy.window_size`.
        summarize_older: If `False`, older messages are dropped
            outright instead of summarized -- falls back to the same
            oldest-first pruning every other strategy in this package
            uses. Exists so a caller can disable the model call
            entirely (e.g. for a quick comparison) without switching
            strategy classes.
    """

    def __init__(
        self,
        summarizer: Summarizer,
        tokenizer: Tokenizer,
        keep_recent: int = DEFAULT_KEEP_RECENT,
        summarize_older: bool = True,
    ) -> None:
        if keep_recent < 1:
            raise ValueError(f"keep_recent must be at least 1, got {keep_recent}")
        self._summarizer = summarizer
        self._tokenizer = tokenizer
        self._keep_recent = keep_recent
        self._summarize_older = summarize_older

    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult:
        messages = list(messages)

        if len(messages) <= self._keep_recent or not self._summarize_older:
            return self._prune_oldest_first(messages, budget)

        older = messages[: -self._keep_recent]
        recent = list(messages[-self._keep_recent :])

        summary_text = self._summarizer.summarize(older)
        summary_message = Message(
            role="system",
            content=summary_text,
            token_count=self._tokenizer.estimate_tokens(summary_text),
        )

        excluded: list[Message] = list(older)
        while len(recent) > 1 and total_tokens([summary_message, *recent]) > budget.effective_limit:
            excluded.append(recent.pop(0))

        return ContextResult(messages=[summary_message, *recent], excluded=excluded)

    @staticmethod
    def _prune_oldest_first(messages: list[Message], budget: TokenBudget) -> ContextResult:
        kept = list(messages)
        excluded: list[Message] = []
        while len(kept) > 1 and total_tokens(kept) > budget.effective_limit:
            excluded.append(kept.pop(0))
        return ContextResult(messages=kept, excluded=excluded)
