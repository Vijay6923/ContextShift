# ContextShift

[![CI](https://github.com/Vijay6923/ContextShift/actions/workflows/ci.yml/badge.svg)](https://github.com/Vijay6923/ContextShift/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Vijay6923/ContextShift/branch/main/graph/badge.svg)](https://codecov.io/gh/Vijay6923/ContextShift)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A Python framework for context engineering: pluggable, benchmarkable
strategies for deciding what an LLM sees under a token budget.**

## Does it actually work? The needle-retention benchmark

Message and token counts alone can't show whether a strategy is any
good — a strategy that reports "kept 10 messages" because
`window_size=10` isn't a finding, it's the constructor argument restated.
The real question: when a strategy drops messages, does it drop the
ones a later question in the conversation actually depends on?

`run_needle_benchmark()` answers this directly, against 49 hand-annotated
fixture conversations covering named failure modes (topic drift,
interleaved threads, corrections, pinned instructions under pressure,
long tool output, and more — see
[`tests/fixtures/conversations/README.md`](tests/fixtures/conversations/README.md)).
Each fixture is annotated with which exact messages a probe question
depends on *before* any strategy runs against it — see
[ADR 0013](docs/decisions/0013-needle-retention-benchmark.md) for the
fixture-honesty discipline behind that ordering. No model call, no
network — fully deterministic and reproducible with the command below.

**The actual finding: every strategy loses more than half of what the
55 probes in this suite depend on. None exceeds 40%.**
`PinnedRecencyStrategy` is the best of the three below, not a strategy
that has solved the problem — read the table as "how bad is each
option," not "which one wins."

| Strategy | Needle Retention | Probes Satisfied | % Tokens Retained |
| --- | --- | --- | --- |
| `PinnedRecencyStrategy(recent_buffer=6)` | **22 / 55 (40.00%)** | 22 / 55 | 36.10% |
| `RecencyStrategy()` | 14 / 55 (25.45%) | 14 / 55 | 35.89% |
| `SlidingWindowStrategy(window_size=10)` | 7 / 55 (12.73%) | 7 / 55 | 20.99% |

*(`TokenBudget(max_tokens=350, safety_margin=50)`, all 49 fixtures.
Reproduce directly:*

```bash
python -m contextshift.benchmark --suite needle
```

*(or the same call via the library API — see [`contextshift/benchmark/__main__.py`](contextshift/benchmark/__main__.py)
for exactly what that command runs.)*

The two rankings also disagree with each other: `PinnedRecencyStrategy`
and `RecencyStrategy` retain almost the same share of *tokens* (36.10%
vs. 35.89%) while differing sharply on needle retention (40.00% vs.
25.45%) — exactly the distinction token/message counts alone can't
surface.

`SummarizationStrategy` is deliberately not in this table — needle
retention's identity-based matching can't give it a meaningful score
without a real `Summarizer` making a real model call, which this
deterministic tier never does. See the
[ADR 0015 addendum](docs/decisions/0015-summarization-strategy.md#addendum-summarizationstrategy-is-excluded-from-the-published-needle-retention-table)
for why, and `run_judged_benchmark()` for the tier that actually
answers whether it works.

### Prior art

"Needle" evaluation isn't a new idea — it borrows its name and its
central question from
[needle-in-a-haystack](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)
and [RULER](https://arxiv.org/abs/2404.06654), and sits alongside
research benchmarks like [LoCoMo](https://arxiv.org/abs/2402.17753),
[LongMemEval](https://arxiv.org/abs/2410.10813),
[LoCoEval](https://arxiv.org/abs/2603.06358), and
[AMemGym](https://arxiv.org/abs/2603.01966). What's different here: this
benchmark tests a *context-selection strategy*, not a model's long-context
recall or a memory system's retrieval quality, and needs zero model calls
to produce a number. ContextShift itself is scoped narrower than memory
backends like [Mem0](https://github.com/mem0ai/mem0) or
[Letta](https://github.com/letta-ai/letta) — no persistence, no session
concept, just deciding what fits a budget this turn. See
[`docs/prior-art.md`](docs/prior-art.md) for the full picture, including
what motivates the cache-aware strategy on the roadmap.

## Installation

```bash
pip install contextshift
```

## Quick Start

```python
from contextshift import ContextManager
from contextshift.core import TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.testing import FakeLLMProvider
from contextshift.tokenizers import HeuristicTokenizer

manager = ContextManager(
    strategy=PinnedRecencyStrategy(recent_buffer=2),
    provider=FakeLLMProvider(complete_response="Paris."),
    tokenizer=HeuristicTokenizer(),
    budget=TokenBudget(max_tokens=100, safety_margin=10),
)

result = manager.chat([], "What's the capital of France?")
print(result.response)          # "Paris."
print(result.context.messages)  # what the strategy kept
```

Swap `FakeLLMProvider` for `contextshift.llm.GroqProvider` (or any other
`LLMProvider`) to call a real model — no other code changes. A fuller,
runnable version, including that swap, is in
[`examples/quickstart.py`](examples/quickstart.py):

```bash
python examples/quickstart.py
```

## Context Strategies

| Strategy | Policy | Pinning | Use when |
|---|---|---|---|
| `PinnedRecencyStrategy` | Protects a fixed recency window and all pinned messages; prunes older messages first, budget-driven | Yes | Some messages (system instructions, user-starred content) must never be dropped regardless of age |
| `RecencyStrategy` | Keeps as much of the conversation's tail as fits the budget — no fixed window, no configuration | No | The simplest baseline: pure recency, nothing else |
| `SlidingWindowStrategy` | Keeps a fixed number of the most recent messages by count; budget is a secondary ceiling on that window | No | A predictable message count matters more than fully using the available budget |
| `SummarizationStrategy` | Keeps a recent window verbatim; compresses everything older into one summary message via a `Summarizer`, instead of discarding it | No | Older context still matters, and the cost of a model call to compress it is acceptable — see [ADR 0015](docs/decisions/0015-summarization-strategy.md) for what this trades off |

All four implement the same `ContextStrategy` protocol
(`build(messages, budget) -> ContextResult`) and are drop-in
replacements for each other — swapping strategies never requires
changing `ContextManager`, another strategy, or the application that
consumes them.

## Benchmarking

`contextshift.benchmark` has two tiers. The deterministic tier (no
network, no model call) runs every strategy against identical input:

```python
from contextshift.benchmark import run_benchmark, to_markdown
from contextshift.strategies import PinnedRecencyStrategy, RecencyStrategy, SlidingWindowStrategy

results = run_benchmark(
    conversation,
    budget,
    [RecencyStrategy(), SlidingWindowStrategy(window_size=10), PinnedRecencyStrategy(recent_buffer=6)],
)
print(to_markdown(results))
```

```
| Strategy | Kept | Discarded | Tokens Kept | Tokens Discarded | % Retained | Latency (s) |
| --- | --- | --- | --- | --- | --- | --- |
| RecencyStrategy | 32 | 9 | 880 | 228 | 79.42% | 0.000024 |
| SlidingWindowStrategy | 10 | 31 | 275 | 833 | 24.82% | 0.000004 |
| PinnedRecencyStrategy | 33 | 8 | 888 | 220 | 80.14% | 0.000028 |
```

`run_needle_benchmark()` (above the fold, at the top of this README)
runs the same deterministic tier against the annotated fixture suite
instead of a bare conversation. `run_judged_benchmark()` is a separate,
explicitly opt-in tier that asks a real `LLMProvider` each probe's
question and scores the answer — the question needle retention is a
*proxy* for — reported as mean/stdev over repeated runs, never a single
number, and never invoked unless a caller supplies both a provider and
a judge. `to_csv()` renders any of these as CSV.

## Tokenizers

`HeuristicTokenizer` (word-count based, zero dependencies) is the
default, and its accuracy is measured rather than left implied:

| Tokenizer | Mean Abs. Error | Mean % Error | Max % Error |
| --- | --- | --- | --- |
| `HeuristicTokenizer` | 9.60 | 27.77% | 93.33% |
| `TiktokenTokenizer` | 0.00 | 0.00% | 0.00% |

*(10-sample corpus; reproduce with `python -m contextshift.benchmark --suite tokenizer`.)*

`TiktokenTokenizer` (`pip install contextshift[tiktoken]`) and
`AnthropicTokenizer` (`pip install contextshift[anthropic]`, calls a
real counting endpoint) are drop-in replacements when that ~28% mean
error, spiking to worst-case near 100% on a single input, is more than
a given budget can tolerate. See
[ADR 0014](docs/decisions/0014-accurate-tokenizers.md) for the full
measurement and how to reproduce it.

Constructing `HeuristicTokenizer` warns once per process
(`HeuristicTokenizerAccuracyWarning`), pointing at the two alternatives
above — silence it with
`warnings.filterwarnings("ignore", category=HeuristicTokenizerAccuracyWarning)`
once you've deliberately chosen this tradeoff. See
[ADR 0017](docs/decisions/0017-heuristic-tokenizer-safety-default.md).

## Vision

`VisionProvider` (`describe(image_bytes, mime_type, prompt=None) -> str`)
is a separate capability from `LLMProvider`, not an extension of it — a
vision call takes a single image and prompt, not a conversation history.
`GeminiVisionProvider` is the current implementation; it never
preprocesses an image itself — every call routes through
`contextshift.ingestion.prepare_image_for_vision()` first.

## Testing

`contextshift.testing.FakeLLMProvider` and `FakeSummarizer` are
in-memory stand-ins for `LLMProvider` and `Summarizer` — no network
calls, no API key, no HTTP. They exist so a CLI, a notebook, an eval
harness, or this repository's own test suite can build and test code
against ContextShift without a real model behind it.

```python
from contextshift.testing import FakeLLMProvider

provider = FakeLLMProvider(complete_response="mocked reply")
provider.complete([...])  # -> "mocked reply", no network involved
```

## Project Structure

```
contextshift/           The framework. Zero Flask/SQLAlchemy dependency.
  core/                   Message, TokenBudget — plain domain types
  tokenizers/             Tokenizer protocol + Heuristic/Tiktoken/Anthropic
  strategies/             ContextStrategy protocol + four strategies
  llm/                    LLMProvider protocol + GroqProvider
  vision/                 VisionProvider protocol + GeminiVisionProvider
  summarization/          Summarizer, built on LLMProvider
  ingestion/              PDF extraction, image preprocessing
  benchmark/              Deterministic + opt-in ContextStrategy comparison
  manager.py              ContextManager — orchestration entry point
  testing.py              FakeLLMProvider, FakeSummarizer — public test doubles

examples/
  quickstart.py            Small, runnable, standalone usage example.
  flask-chat/               A real Flask chat app built on contextshift
                             (see its own README) — a consumer of the
                             library, not the library itself.

docs/
  architecture.md         The current architecture: layers, dependency
                           rules, diagrams.
  philosophy.md             Scope, what's deliberately out of scope, and
                             the design principles behind the library.
  decisions/               Architecture Decision Records — why specific
                            choices were made.
  roadmap.md                 Where the project is headed.

tests/                   Test suite for contextshift/ itself — no Flask,
                         no database, no network required.
  fixtures/
    conversations/          Hand-annotated needle-retention fixtures.
    legacy/                 Pre-refactor implementations, kept only as
                             characterization-test fixtures.
```

## Documentation

- [`docs/philosophy.md`](docs/philosophy.md) — what this project is
  for, what it deliberately doesn't do, and the principles behind it.
- [`docs/architecture.md`](docs/architecture.md) — the current
  architecture: layers, dependency rules, diagrams.
- [`docs/decisions/`](docs/decisions/) — Architecture Decision
  Records, in numeric order, tracing the library's evolution from a
  single-file Flask application into this framework.
- [`docs/roadmap.md`](docs/roadmap.md) — what's done and what's next.
- [`docs/versioning.md`](docs/versioning.md) — the semver policy, and
  what's actually protocol-stable pre-1.0.
- [`docs/benchmarks/`](docs/benchmarks/) — committed, literal output of
  every benchmark suite, regenerable with
  `python -m contextshift.benchmark`.

All of the above is also published as a browsable site via
[`mkdocs.yml`](mkdocs.yml) (Material for MkDocs) — build it locally with
`pip install -e ".[docs]" && mkdocs serve`; `.github/workflows/docs.yml`
deploys it to GitHub Pages on push to `main` once Pages is enabled for
this repository (Settings → Pages → Source: GitHub Actions).

## Example Application

[`examples/flask-chat/`](examples/flask-chat/) is a real Flask chat
app — streaming chat, PDF upload, image analysis, pinning, and
summarization — built entirely on `contextshift/`. See its own
[README](examples/flask-chat/README.md) for setup; a live deployment
runs at [context-shift.vercel.app](https://context-shift.vercel.app/).

## Running the Tests

```bash
pip install -r requirements-dev.txt
pytest
pyflakes contextshift/ tests/ examples/flask-chat/app.py examples/flask-chat/adapters.py examples/flask-chat/models.py examples/flask-chat/config.py
ruff check .
mypy --strict contextshift/
```

A plain `pytest` from the repository root runs both the library's own
suite (`tests/` — no Flask, no database, no network) and the example
app's route-level suite
([`examples/flask-chat/tests/`](examples/flask-chat/tests/)) together.
`ruff` and `mypy --strict` are exactly what CI runs
(`.github/workflows/ci.yml`), so a clean local run means CI will be
clean too.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues and pull requests are
welcome — an issue describing what you'd like to change before starting
on a pull request is the best way to check it fits the architecture in
[`docs/architecture.md`](docs/architecture.md).

## Security

See [`SECURITY.md`](SECURITY.md). `.env` (containing API keys) and
local database files are excluded via `.gitignore` and never
committed.

## License

MIT — see [`LICENSE`](LICENSE).
