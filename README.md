# ContextShift

**A framework for context engineering: pluggable strategies for deciding what an LLM sees.**

ContextShift is a Python library for managing conversation context under a
token budget — selecting which messages an LLM should see, summarizing what
doesn't fit, and talking to any model provider through a single, swappable
interface. A small Flask chat application in this repository is built on
top of the framework, as a worked example of using it — it is not the
project.

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

The example app additionally needs Flask and a Groq API key.

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY
python app.py
```

Open `http://localhost:5000`. A live deployment is also running at
**[context-shift.vercel.app](https://context-shift.vercel.app/)**.

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

`.env` (containing your `GROQ_API_KEY`) and local database files are
excluded via `.gitignore` and never uploaded to version control. Keep your
`.env` file private.

## License

MIT — see [`LICENSE`](LICENSE).
