# Committed benchmark results

Each file here is the literal, unedited output of one
`python -m contextshift.benchmark` suite, committed so a reader can
compare what's published in the [project README](https://github.com/Vijay6923/ContextShift#readme) and
[`docs/decisions/`](../decisions/) against a real run without having to
execute anything first — and so a future run that produces a
*different* result is a visible, reviewable diff, not a silent drift.

| File | Command | Backs |
| --- | --- | --- |
| [`standard.md`](standard.md) | `python -m contextshift.benchmark --suite standard` | The illustrative messages/tokens-kept table in README.md's Benchmarking section |
| [`needle.md`](needle.md) | `python -m contextshift.benchmark --suite needle` | README.md's needle-retention table and [ADR 0013](../decisions/0013-needle-retention-benchmark.md) |
| [`tokenizer.md`](tokenizer.md) | `python -m contextshift.benchmark --suite tokenizer` | README.md's Tokenizers table and [ADR 0014](../decisions/0014-accurate-tokenizers.md) |

## Regenerating

```bash
pip install -r requirements-dev.txt   # tiktoken is required for the tokenizer suite
python -m contextshift.benchmark --suite standard > docs/benchmarks/standard.md
python -m contextshift.benchmark --suite needle > docs/benchmarks/needle.md
python -m contextshift.benchmark --suite tokenizer > docs/benchmarks/tokenizer.md
```

## What's stable here, and what isn't

Message counts, token counts, needle-retention percentages, and
tokenizer error rates are deterministic — the same input and the same
code always produce the same number, on any machine. **Latency is
not** — it reflects whatever hardware happened to run the command, and
is included because `BenchmarkResult` reports it, not because a
specific latency value is a claim this project makes about strategy
performance in general.

Last generated: 2026-08-09, against the fixture suite and strategies
present in the repository at that commit.
