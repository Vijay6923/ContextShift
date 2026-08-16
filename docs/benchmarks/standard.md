# Standard benchmark

`python -m contextshift.benchmark --suite standard`

`TokenBudget(max_tokens=8000, safety_margin=500)`, run against all 49
fixtures in `tests/fixtures/conversations/` concatenated into one
2232-message conversation.

| Strategy | Kept | Discarded | Tokens Kept | Tokens Discarded | % Retained | Latency (s) |
| --- | --- | --- | --- | --- | --- | --- |
| RecencyStrategy | 376 | 1856 | 7483 | 31665 | 19.11% | 0.095019 |
| SlidingWindowStrategy | 10 | 2222 | 214 | 38934 | 0.55% | 0.000033 |
| PinnedRecencyStrategy | 380 | 1852 | 7498 | 31650 | 19.15% | 0.108332 |

These metrics are each implied by the strategy's own definition (see
[ADR 0013](../decisions/0013-needle-retention-benchmark.md)) — useful
for understanding *how much* of a budget a strategy consumes, not
whether what it kept was the right thing to keep. See
[`needle.md`](needle.md) for the non-tautological comparison.
