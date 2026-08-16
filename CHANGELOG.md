# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Nothing has been published to PyPI yet; the `[Unreleased]` section
below covers everything built so far.

## [Unreleased]

### Added

- `ContextManager` — composes a `ContextStrategy`, a `Tokenizer`, and an
  `LLMProvider` into a single chat turn (`chat()` / `stream_chat()`).
- Four `ContextStrategy` implementations: `PinnedRecencyStrategy`,
  `RecencyStrategy`, `SlidingWindowStrategy`, and `SummarizationStrategy`
  (compresses older messages into a summary via a `Summarizer` instead
  of discarding them — see
  [ADR 0015](docs/decisions/0015-summarization-strategy.md)).
- `Tokenizer` implementations: `HeuristicTokenizer` (zero-dependency
  default), `TiktokenTokenizer` (`pip install contextshift[tiktoken]`),
  and `AnthropicTokenizer` (`pip install contextshift[anthropic]`) — see
  [ADR 0014](docs/decisions/0014-accurate-tokenizers.md) for the
  heuristic's measured error rate against the other two.
- `LLMProvider` (`GroqProvider`) and `VisionProvider`
  (`GeminiVisionProvider`) — vendor-neutral interfaces with one concrete
  implementation each.
- `Summarizer` — an LLM-based conversation-summarization domain
  service, built on `LLMProvider`.
- `contextshift.ingestion` — PDF text extraction and image
  preprocessing, as pure functions with no model dependency.
- `contextshift.benchmark` — deterministic `ContextStrategy` comparison
  (`run_benchmark`), needle-retention benchmarking against a
  hand-annotated fixture suite (`run_needle_benchmark`, 49 fixtures
  covering named failure modes — see
  [ADR 0013](docs/decisions/0013-needle-retention-benchmark.md)), a
  separate opt-in LLM-scored judge tier (`run_judged_benchmark`), and a
  tokenizer-accuracy benchmark (`benchmark_tokenizers`).
- `contextshift.testing` — public `FakeLLMProvider` and
  `FakeSummarizer` test doubles, for building and testing against
  ContextShift with no network access.
- [`examples/flask-chat/`](examples/flask-chat/) — a real Flask chat
  application (streaming chat, PDF upload, image analysis, pinning,
  summarization) built entirely on `contextshift/`, with its own test
  suite and README.
- [`docs/prior-art.md`](docs/prior-art.md) — needle-in-a-haystack,
  RULER, LoCoMo, LongMemEval, LoCoEval, AMemGym, TokenPilot, Mem0,
  LangChain, and Letta/MemGPT, and how this project's scope differs
  from each.
- `HeuristicTokenizerAccuracyWarning` — `HeuristicTokenizer` now warns
  once per process on construction, pointing at `TiktokenTokenizer`/
  `AnthropicTokenizer` — see
  [ADR 0017](docs/decisions/0017-heuristic-tokenizer-safety-default.md).
- `BenchmarkResult.needle_retained_count` / `needle_total_count` —
  `to_markdown()`'s "Needle Retention" column now renders as
  `"14 / 55 (25.45%)"`, not a bare percentage, so the sample size
  is never hidden behind the percentage.

### Changed

- Repository restructured so the root contains only `contextshift/`,
  `tests/`, `docs/`, `examples/`, and packaging files — the demo
  application and its pre-refactor reference implementation
  (`utils/` → `tests/fixtures/legacy/`) moved out of the root; see
  [ADR 0016](docs/decisions/0016-repository-shape-for-outside-readers.md).
- The needle-retention fixture suite expanded from 10 to 49
  conversations (55 probes) for broader per-failure-mode coverage; the
  original 10 fixtures are byte-identical to before the expansion. The
  published needle-retention numbers changed accordingly — current
  finding: every shipped strategy loses more than half of what the 55
  probes depend on, and none exceeds 40%.
- `SummarizationStrategy` is excluded from the needle-retention table
  and CLI suite — `FakeSummarizer`'s placeholder text can't produce a
  meaningful score under identity-based matching. See the
  [ADR 0015 addendum](docs/decisions/0015-summarization-strategy.md#addendum-summarizationstrategy-is-excluded-from-the-published-needle-retention-table)
  for the reasoning and how to evaluate it properly, via
  `run_judged_benchmark()` with a real `Summarizer`.
