# ContextShift

**A framework for context engineering: pluggable strategies for deciding what an LLM sees.**

ContextShift is a Python library for managing conversation context under a
token budget — selecting which messages an LLM should see, summarizing what
doesn't fit, and talking to any model provider through a single, swappable
interface. A small Flask chat application in this repository is built on
top of the framework, as a worked example of using it — it is not the
project.

## Features

- **Intelligent context management** — a pluggable strategy decides which
  messages an LLM sees under a token budget, instead of naively replaying
  the entire conversation on every turn.
- **Token-aware context pruning** — older messages are pruned first, pinned
  messages are never dropped, and every pruning decision is inspectable on
  the result, not hidden inside a side effect.
- **Modular ContextShift architecture** — strategies, tokenizers,
  summarization, and LLM providers are independent, swappable interfaces
  with no dependency on Flask, SQLAlchemy, or each other's implementation.
- **Groq-powered chat** — fast, streaming chat completions.
- **Gemini-powered image understanding and OCR** — image uploads are
  analyzed and transcribed by Google Gemini.
- **PDF ingestion** — text extraction from uploaded PDFs, with no model
  dependency at all.
- **Image upload support** — with automatic resizing, format normalization,
  and compression before analysis.
- **Comprehensive automated test suite** — 271 tests covering the library,
  the example application, and byte-for-byte characterization tests proving
  ported logic matches its original behavior exactly (see
  [Testing](#testing)).
- **Open-source friendly project structure** — a clean separation between
  the reusable framework (`contextshift/`) and the example application, a
  documented architecture with recorded design decisions, and an
  installable package (`pyproject.toml`).

## Overview

Most LLM applications eventually hit the same wall: a conversation grows
past what fits in a model's context window, or past what's worth paying to
send on every turn. The usual fix is ad hoc — truncate the oldest messages,
maybe summarize occasionally, hope for the best — implemented once, inline,
tangled up with whatever web framework and database the application
happens to use.

ContextShift factors that decision out into its own layer. A **strategy**
decides which messages belong in context under a given token budget. A
**summarizer** decides what to ask a model when compressing history. A
**provider** decides how to actually talk to a specific model. None of
these know about each other's implementation, none of them know a web
framework exists, and each is swappable independently — a new strategy, a
new model provider, or a different summarization approach is a new class
implementing a small interface, not a change to the other two.

## Motivation

**A large context window is not the same thing as memory.** Sending an
entire conversation history to a model on every turn doesn't solve
long-conversation coherence — it just delays the point where a real
context-management decision becomes necessary, and it does so at
increasing cost and latency. Developers still need a deliberate policy for
what a model sees: what to keep, what to compress, what to drop. ContextShift
exists to make that policy explicit, inspectable, and swappable, instead of
implicit and buried in application code.

## Key capabilities

- **Pluggable context-selection strategies** — a `ContextStrategy` selects
  which messages fit a `TokenBudget`. Ships with `PinnedRecencyStrategy`
  (always keep pinned messages and the most recent window; prune older
  messages first). Every decision a strategy makes — what it kept, what it
  excluded — is inspectable on the result it returns, not hidden inside a
  side effect.
- **Vendor-neutral LLM provider abstraction** — an `LLMProvider` exposes
  `complete()`/`stream()` with nothing vendor-specific in its public shape.
  Ships with `GroqProvider`. A second provider is a class implementing two
  methods; nothing that depends on `LLMProvider` needs to change.
- **Summarization as a domain service** — `Summarizer` expresses *what* to
  ask a model to compress a conversation, depending only on the
  `LLMProvider` interface, never a concrete provider.
- **Token estimation** — a `Tokenizer` protocol with a heuristic
  implementation, decoupled from everything that consumes its output.
- **Document ingestion** — PDF text extraction and image preprocessing for
  vision models, as pure functions with no network dependency and no
  application-specific types.
- **Everything is a small `Protocol`** — strategies, providers, and
  tokenizers are structural interfaces, not base classes. A conforming
  implementation needs no dependency on ContextShift itself, and every
  interface has a trivial fake implementation usable in tests with zero
  network access.

## Architecture overview

At the level of "where does a request actually go" in the example
application:

```
                        User
                         │
                         ▼
                Flask Application
                         │
        ┌────────────────┼──────────────────┬─────────────────┐
        ▼                ▼                  ▼                 ▼
   Chat / Summarize   Image Upload      PDF Upload      Context Selection
        │                │                  │                 │
        ▼                ▼                  ▼                 ▼
      Groq            Gemini        contextshift.ingestion   contextshift.strategies
   (LLMProvider)   (vision + OCR,     (pure text extraction,   (PinnedRecencyStrategy,
                    called directly    no model involved)       via contextshift.core)
                    from the app --
                    see below)
```

Chat, summarization, and PDF-upload text generation all go through
`contextshift/` (via `adapters.py`). Image analysis is the one path that
does not: it calls Google Gemini directly from the example application,
because `contextshift` doesn't have a vision abstraction yet (see
[`docs/decisions/0010-multimodal-architecture-review.md`](docs/decisions/0010-multimodal-architecture-review.md)
for why, and what one would look like).

Underneath "context selection," the library itself is organized into four
layers, each answering a different question:

```
Context Engineering   strategies/        "what context should the model see?"
        │
LLM Services          summarization/     "what should I ask the model?"
        │
LLM Infrastructure    llm/               "how do I talk to a model?"
        │
Transport             HTTP (inside llm/) "how do bytes move across the network?"

All of the above build on:
Core Types             core/             Message, TokenBudget — plain,
                                          dependency-free domain types
```

Dependencies flow one direction only, top to bottom. `contextshift/` has no
dependency on Flask, SQLAlchemy, or any web framework — it's designed to be
equally usable from a web app, a CLI, a notebook, or an evaluation harness.
The example Flask application is one consumer, connected through a small
adapter layer (`adapters.py`) that translates between the application's
database rows and the library's plain domain types; the library itself has
no awareness that the application exists.

Full reasoning for every architectural decision — not just what the
architecture is, but why — is in [`docs/architecture.md`](docs/architecture.md)
and [`docs/decisions/`](docs/decisions/).

## Repository layout

```
contextshift/          The framework. Zero Flask/SQLAlchemy dependency.
  core/                 Message, TokenBudget — plain domain types
  tokenizers/            Tokenizer protocol + HeuristicTokenizer
  strategies/             ContextStrategy protocol + PinnedRecencyStrategy
  llm/                     LLMProvider protocol + GroqProvider
  summarization/            Summarizer, built on LLMProvider
  ingestion/                 PDF extraction, image preprocessing

examples/               Small, runnable, standalone usage examples.

docs/
  architecture.md        The current architecture: layers, dependency
                          rules, guiding principles.
  decisions/              Architecture Decision Records — why specific
                           choices were made.
  diagrams/                 Mermaid source for the architecture diagrams.
  roadmap.md                Where the project is headed.

tests/                  Test suite for contextshift/ and the example app.

app.py, adapters.py,     The example Flask application: a chat UI
models.py, config.py,    demonstrating ContextShift in a real, working
templates/, static/      product. Not the framework itself.

utils/                  Example-app-only code not yet part of the
                         framework: image understanding via Google Gemini
                         (see Image Processing above and
                         docs/decisions/0010-multimodal-architecture-review.md).
```

## Quick start

### Install the framework

```bash
git clone <this-repository-url>
cd ContextShift
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

This installs `contextshift` and its runtime dependencies (`requests`,
`PyPDF2`, `Pillow`) in editable mode, so you can `import contextshift` from
anywhere in the environment.

### Run the example chat application

The example app additionally needs Flask and two API keys (see
[Environment Variables](#environment-variables) below for what each does).

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in GROQ_API_KEY and GEMINI_API_KEY
python app.py
```

Open `http://localhost:5000`. A live deployment is also running at
**[context-shift.vercel.app](https://context-shift.vercel.app/)**.

### Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

See [Testing](#testing) below for what's covered and the current status.

## Environment Variables

| Variable | Required | Used for |
|---|---|---|
| `GROQ_API_KEY` | Yes | Chat and summarization (`GroqProvider`, via Groq's API). |
| `GEMINI_API_KEY` | Only for image upload | Image understanding and OCR (`analyze_image_with_gemini`, via Google Gemini). Chat, summarization, and PDF upload work without it. |
| `FLASK_DEBUG` | No (default `true`) | Enables Flask's debug/reload mode. |
| `FLASK_PORT` | No (default `5000`) | Port the example app listens on. |
| `DATABASE_URL` | No (defaults to local SQLite) | Overrides the database connection string, e.g. for Postgres in production. |

Get a Groq key at [console.groq.com](https://console.groq.com/) and a
Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
Copy `.env.example` to `.env` and fill these in — `.env` is gitignored and
never committed.

```bash
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_api_key
```

## Image Processing

- **Chat generation uses Groq.** Text completions and summarization always
  go through `GroqProvider` — unaffected by the Gemini migration below.
- **Images are processed using Google Gemini** (`analyze_image_with_gemini`
  in `utils/file_processor.py`), not through the `contextshift` library --
  see [Architecture overview](#architecture-overview) for why.
- **Images are resized and optimized before analysis**: palette/RGBA
  images are converted to RGB, anything larger than 1568px on the longest
  side is downscaled, and the result is re-encoded as JPEG before being
  sent to Gemini. This preprocessing has no model dependency and runs
  identically regardless of which vision provider is behind it.
- **PDF uploads never touch a vision model at all** — text is extracted
  directly (`contextshift.ingestion.extract_text_from_pdf`) and the
  extracted text is sent through the normal Groq chat path.

## Minimal usage example

```python
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.summarization import Summarizer

# Messages are the framework's plain, framework-agnostic domain type.
conversation = [
    Message(role="user", content="What's the capital of France?", token_count=8),
    Message(role="assistant", content="Paris.", token_count=3),
    Message(role="user", content="And its population?", token_count=6),
]

# A strategy decides which messages fit a token budget.
budget = TokenBudget(max_tokens=100, safety_margin=10)
result = PinnedRecencyStrategy(recent_buffer=2).build(conversation, budget)
print([m.content for m in result.messages])   # kept
print([m.content for m in result.excluded])   # dropped

# Summarizer depends only on the LLMProvider protocol -- any object with
# complete()/stream() methods works, including a fake with no network.
class EchoProvider:
    def complete(self, messages, max_tokens=1024):
        return f"[{len(list(messages))} messages summarized]"
    def stream(self, messages, max_tokens=1024):
        yield self.complete(messages, max_tokens)

print(Summarizer(EchoProvider()).summarize(conversation))
```

A fuller, runnable version of this — including how to swap in the real
`GroqProvider` — is in [`examples/quickstart.py`](examples/quickstart.py):

```bash
python examples/quickstart.py
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — the current architecture:
  layers, dependency rules, guiding principles.
- [`docs/decisions/`](docs/decisions/) — Architecture Decision Records
  explaining why specific design choices were made, including the ones
  that were considered and deliberately rejected.
- [`docs/diagrams/`](docs/diagrams/) — Mermaid source for the architecture
  diagrams.
- [`docs/roadmap.md`](docs/roadmap.md) — where the project is headed.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

**271 tests pass, 0 failures** (obtained by running the suite; re-run it
yourself to confirm, this number will drift as the project grows). Coverage
spans:

- Every Flask route in the example application.
- The `contextshift` library's types, strategies, tokenizers, LLM provider
  abstraction, summarization, and ingestion modules, independent of Flask
  and with no network access required (fake providers satisfy every
  interface).
- **Characterization tests** that proved ported/migrated logic behaves
  identically to what it replaced — e.g. the Gemini image-preprocessing
  path is verified byte-for-byte against what actually gets sent to the
  model, not just "does it return something."

## Recent Improvements

- **Replaced Groq Vision with Google Gemini** for image understanding and
  OCR — chat and summarization are unaffected and continue to use Groq.
- **Modernized the image pipeline**: migrated to the official `google-genai`
  SDK, raw image bytes are sent directly (no manual base64 encoding), and
  retry/timeout handling is now managed by the SDK's built-in retry options
  instead of a hand-rolled loop.
- **Added a dedicated Gemini test suite** (`tests/test_gemini_vision.py`)
  covering the new code path's error handling, prompts, and request shape,
  plus updated the existing characterization tests to verify the
  preprocessing step is byte-for-byte unchanged by the vendor swap.
- **Improved project documentation**: a framework-first README, a current
  (not historical) `docs/architecture.md`, an installable package
  (`pyproject.toml`), and a runnable quick-start example
  (`examples/quickstart.py`).

## Roadmap summary

The core framework — strategies, tokenizers, summarization, LLM provider
abstraction, and document ingestion — is complete and covers everything the
example application needs for text-based chat, summarization, and PDF
upload. Two things are explicitly not built yet, by design rather than
oversight:

- **A second context-selection strategy.** Only `PinnedRecencyStrategy`
  exists today; the framework is built to add more (semantic retrieval,
  importance scoring, hybrid policies) without changing existing code, but
  none are implemented yet.
- **A dedicated vision/image-understanding capability.** Image analysis in
  the example app still calls a vendor API directly rather than going
  through a library abstraction — seeing why, and what such an abstraction
  should look like, is worked out in
  [`docs/decisions/0010-multimodal-architecture-review.md`](docs/decisions/0010-multimodal-architecture-review.md).

See [`docs/roadmap.md`](docs/roadmap.md) for the full picture.

## Contributing

Issues and pull requests are welcome. There's no formal contribution guide
yet — for now, an issue describing what you'd like to change before
starting on a pull request is the best way to check it fits the
architecture in [`docs/architecture.md`](docs/architecture.md).

## Security note

`.env` (containing your `GROQ_API_KEY` and `GEMINI_API_KEY`) and local
database files are excluded via `.gitignore` and never uploaded to version
control. Keep your `.env` file private.

## License

MIT — see [`LICENSE`](LICENSE).
