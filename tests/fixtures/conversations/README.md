# Needle-retention fixtures

Each `.json` file here is a hand-authored conversation plus one or more
*probes* — a question, and the exact messages (by index) that are
load-bearing for answering it correctly. `contextshift.benchmark.needle`
runs a strategy over the conversation and checks whether those specific
messages survived selection. See
[`docs/decisions/0013-needle-retention-benchmark.md`](../../../docs/decisions/0013-needle-retention-benchmark.md)
for the full reasoning.

## Why this exists

A strategy's own metrics (messages kept, tokens kept) are tautological:
`SlidingWindowStrategy(window_size=10)` keeping 10 messages restates its
own definition, not a finding. The question worth asking is whether a
strategy drops the messages a real question actually depends on. That's
answerable without a model call, as long as "load-bearing" was decided
once, by a human, *before* any strategy ever ran against the fixture —
never inferred at benchmark time, and never adjusted after seeing how a
particular strategy performs.

## Format

```json
{
  "name": "early-establishment",
  "failure_mode": "early-establishment",
  "description": "One sentence on what this fixture is designed to expose.",
  "messages": [
    {"role": "user", "content": "...", "token_count": 12, "is_pinned": false}
  ],
  "probes": [
    {
      "question": "What did the user say?",
      "load_bearing_indices": [0],
      "expected_answer": "optional, only used by the opt-in LLM-scored tier"
    }
  ]
}
```

`token_count` is required per message (fixtures are meant to be
budget-aware, the same as any real conversation). `is_pinned` defaults
to `false`. `expected_answer` is optional — the deterministic
needle-retention tier never reads it; only
`contextshift.benchmark.judge.run_judged_benchmark()` (the opt-in tier)
does.

## Failure modes covered

- **early-establishment** — a fact set near the start of a long
  conversation, referenced only much later, with nothing but unrelated
  filler in between.
- **topic-drift** — the conversation moves through several unrelated
  topics after an early decision, then circles back to it.
- **interleaved-threads** — two or more unrelated threads interleaved
  turn by turn; the answer depends on one message from only one thread.
- **correction-of-earlier-answer** — a fact is stated, then explicitly
  corrected later. The correct answer depends on the correction
  surviving, not the original (now-wrong) statement.
- **long-tool-output** — one very large message (a log dump) contains a
  small detail the eventual question depends on.
- **pinned-instruction-under-pressure** — a pinned instruction sits at
  the start of a conversation long enough to force it out under a tight
  budget if it weren't pinned.

## Adding a fixture

1. Write the conversation and annotate probes *before* running any
   strategy against it — annotating after looking at a strategy's
   output risks unconsciously favoring whichever strategy you're
   testing.
2. Validate it loads: `python -c "from pathlib import Path; from contextshift.benchmark.probes import load_fixture; load_fixture(Path('your-file.json'))"`.
3. Commit fixture additions separately from any strategy or benchmark
   code changes.

`_generate.py` in this directory is the script that produced the
current fixture set — a reference for the format and a way to see how
existing fixtures compute correct message indices, not something the
benchmark or test suite imports.
