# ContextShift Architecture

## Purpose

ContextShift is not a chatbot. The chatbot (the Flask app in
[`examples/flask-chat/`](../examples/flask-chat/)) is a
demonstration and example client for the actual project: **a framework
for experimenting with and comparing LLM context-window management
strategies** — sliding windows, pinning, summarization, semantic retrieval,
importance scoring, and hybrids of these.

The premise the project exists to demonstrate: **a large context window is
not the same thing as memory.** Sending an entire conversation history to a
model doesn't solve long-conversation coherence; it just delays the point
where a management strategy becomes necessary. ContextShift makes that
management explicit, observable, pluggable, and measurable.

`contextshift/` is a standalone Python library that a researcher or another
engineer can use without the Flask app existing at all: in a CLI batch
evaluation harness, a notebook, or a different application entirely. Every
design decision in this document is filtered through one question:

> If the web application disappeared tomorrow, would the `contextshift`
> library still be useful to another developer or researcher?

If the answer is no, the code belongs in the application layer, not the
library.

## Layer diagram

```
Application            examples/flask-chat/{app,models,config}.py — Flask,
                        SQLAlchemy, HTTP routing, persistence, the example
                        chat UI

      ↓ (imports)

Adapters                examples/flask-chat/adapters.py — translates between application-specific
                        types (SQLAlchemy ORM rows, Config) and library-neutral
                        types (contextshift.core.Message). Lives on the
                        application side of the boundary.

      ↓ (imports)

ContextShift Library    manager.py, strategies/, tokenizers/, llm/,
                        vision/, summarization/, ingestion/, testing.py,
                        benchmark/ — the actual context-management logic,
                        zero web-framework dependency

      ↓ (imports)

Core Types              core/ — plain, dependency-free domain types
                        (Message, TokenBudget) that every other library
                        subpackage builds on
```

A machine-readable version of this diagram lives in
[`diagrams/layer-diagram.mmd`](diagrams/layer-diagram.mmd).

### Internal layering within the ContextShift Library

The library's subpackages form distinct responsibilities, each
answering a different question:

```
Orchestration (manager.py)            "run one chat turn: select context,
                                        then call a provider"
            │ composes
    ┌───────┼──────────────┬──────────────────┐
    ▼       ▼               ▼                  ▼
Context     Tokenization   LLM                 Vision (vision/)
Engineering (tokenizers/)  Infrastructure       "describe an image"
(strategies/)              (llm/)                    │
    │                           │                     ▼
    │                           ▼              Ingestion (ingestion/)
    │                    Transport (HTTP,      "prepare bytes -- PDF text,
    │                    inside llm/*.py)       image resize/encode"
    ▼
LLM Services (summarization/)         "what should I ask the model?"
                                       (depends on llm/'s LLMProvider)

Independent of the orchestration chain above:
    Testing (testing.py)      FakeLLMProvider -- depends only on core/
    Benchmark (benchmark/)    compares ContextStrategy implementations --
                               depends on strategies/ and core/
```

`ContextManager` composes a strategy, a tokenizer, and a provider into
one chat turn; it is the only subpackage that depends on three others
at once, which is exactly its job (orchestration) rather than a
layering violation. Strategies decide what context to build;
summarization decides what to ask a model in service of some goal
(today, compression); providers decide how to actually talk to a
specific model; transport is the wire protocol underneath a provider.
Vision is a separate capability from `llm/`, not an extension of it —
a vision call has no conversation history and a structurally different
request shape (see
[`decisions/0010-multimodal-architecture-review.md`](decisions/0010-multimodal-architecture-review.md))
— and depends on `ingestion/` for already-prepared image bytes, never
the reverse. Each dependency runs one direction only (`summarization/`
depends on `llm/`'s `LLMProvider` interface, never on `GroqProvider` or
on HTTP directly; `vision/` depends on `ingestion/`'s output, never
the other way around), and nothing above the transport layer knows
transport-level details exist — `PinnedRecencyStrategy` has no idea an
HTTP request is even possible, and `Summarizer` has no idea Groq
exists. This is the same one-directional dependency principle as the
outer Application → Adapters → Library → Core layering above, applied
a second time, inside the library itself.

## Dependency rules

1. **Dependencies flow one direction only**, top to bottom in the diagram
   above. `contextshift/` never imports from `examples/flask-chat/app.py`,
   `models.py`, `config.py`, or `adapters.py` — the library has zero
   awareness that a Flask application exists, let alone this one.
2. **`contextshift/` has zero dependency on Flask or SQLAlchemy**, or on
   any other application/web framework. Its only third-party dependencies
   are the ones a subpackage genuinely needs (e.g. `requests` for the Groq
   provider, `PyPDF2`/`Pillow` for document ingestion).
3. **Adapters are application-layer code**, not library code, precisely
   because an adapter's job is to know about *both* sides of the boundary
   (an ORM row and a `core.Message`) — code that knows about both sides
   cannot live inside the side that's supposed to know about neither.
   See [`decisions/0001-library-independence-and-adapter-placement.md`](decisions/0001-library-independence-and-adapter-placement.md).
4. **Within `contextshift/`, `core/` is the dependency sink.** Every other
   subpackage may depend on `core/`; `core/` depends on nothing else in the
   package. `strategies/` depends on `core/`. `tokenizers/` depends on
   nothing in the package at all — token estimation operates on a plain
   `str`, not a `Message`. `strategies/` does not depend on `tokenizers/`:
   `PinnedRecencyStrategy` trusts a precomputed `Message.token_count`
   rather than measuring anything itself; a strategy that measures tokens
   on the fly would be the first case of that dependency existing.
   `summarization/` depends on `llm/`'s `LLMProvider` interface (it needs a
   provider to call a model with), never on a concrete provider.
   `ingestion/` depends on nothing in the package — pure functions over
   raw bytes. `vision/` depends on `ingestion/` (a `VisionProvider`
   consumes already-prepared image bytes, never preprocessing them
   itself) but not on `core/` — a vision call has no `Message` history.
   `manager.py` depends on `core/`, `strategies/base`, `llm/base`, and
   `tokenizers/base` — composing them is its entire purpose. `testing.py`
   depends only on `core/`. `benchmark/` depends on `strategies/base` and
   `core/`. No other cross-subpackage dependencies exist; a new one
   should be a deliberate, documented decision, not an incidental import.

## Architectural principles

These apply to every module in `contextshift/`:

- **Every module is public API.** Public classes and functions carry type
  hints. Public modules carry a concise docstring stating their purpose.
  Implementation details that might need to change later are not exposed
  just because it's convenient — a strategy's internal helper functions
  are not public API; its `ContextStrategy.build(...)` entry point is.
- **No premature API surface.** A field, method, or export exists because
  something concretely needs it, not because it might be useful someday.
  Speculative surface is easy to add later and hard to remove once
  something depends on it.
- **Interfaces are structural `Protocol`s, not `ABC`s.** A `Tokenizer`, a
  `ContextStrategy`, an `LLMProvider` is defined entirely by having a
  matching method, not by inheriting from anything in this package. A new
  implementation of any of these needs no dependency on `contextshift`
  itself. See [`decisions/0005-protocol-over-abc.md`](decisions/0005-protocol-over-abc.md).
- **Every layer is independently testable with a fake.** Nothing that
  depends on `LLMProvider`, for instance, needs a real network connection
  or API key to be tested — any object with matching `complete()`/`stream()`
  methods satisfies the interface.
- **Architecturally significant decisions are recorded**, not left
  implicit in code alone. See [`decisions/`](decisions/) for the reasoning
  behind specific choices, including alternatives that were considered and
  rejected.
