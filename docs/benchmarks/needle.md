# Needle-retention benchmark

`python -m contextshift.benchmark --suite needle`

`TokenBudget(max_tokens=350, safety_margin=50)`, run against all 49
hand-annotated fixtures in `tests/fixtures/conversations/` — see
[ADR 0013](../decisions/0013-needle-retention-benchmark.md) for what
this measures and why it isn't tautological the way `standard.md` is.

**The actual finding: every strategy loses more than half of what the
55 probes in this suite depend on. None exceeds 40%.**
`PinnedRecencyStrategy` is the best of the three, not a strategy that
has solved the problem.

| Strategy | Kept | Discarded | Tokens Kept | Tokens Discarded | % Retained | Latency (s) | Needle Retention | Probes Satisfied |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RecencyStrategy | 1037 | 1195 | 14052 | 25096 | 35.89% | 0.001802 | 14 / 55 (25.45%) | 14 / 55 |
| SlidingWindowStrategy | 490 | 1742 | 8219 | 30929 | 20.99% | 0.000100 | 7 / 55 (12.73%) | 7 / 55 |
| PinnedRecencyStrategy | 1044 | 1188 | 14132 | 25016 | 36.10% | 0.002368 | 22 / 55 (40.00%) | 22 / 55 |

`PinnedRecencyStrategy` wins on needle retention despite retaining a
similar share of *tokens* to `RecencyStrategy` — the distinction the
`standard` suite's metrics alone can't surface. But "wins" here means
40% instead of 25% or 13%, not "solves the problem" — a caller whose
strategy needs to actually preserve most load-bearing content under a
tight budget should not read this table as "pin your instructions and
you're done."

`SummarizationStrategy` is not in this table — see the
[ADR 0015 addendum](../decisions/0015-summarization-strategy.md#addendum-summarizationstrategy-is-excluded-from-the-published-needle-retention-table).
