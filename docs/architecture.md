# ContextShift Architecture

## Purpose

ContextShift is not a chatbot. The chatbot (the Flask app in this repo) is a
demonstration and visualization client for the actual project: **a framework
for experimenting with and comparing LLM context-window management
strategies** — sliding windows, pinning, summarization, semantic retrieval,
importance scoring, and hybrids of these.

The premise the project exists to demonstrate and eventually measure:
**a large context window is not the same thing as memory.** Sending an
entire conversation history to a model doesn't solve long-conversation
coherence; it just delays the point where a management strategy becomes
necessary. ContextShift makes that management explicit, observable, and
— as the migration in progress completes — pluggable and measurable.

The long-term goal is for `contextshift/` to stand alone as an installable
Python library that a researcher or another engineer can use without the
Flask app existing at all: in a CLI batch-evaluation harness, a notebook,
or someone else's application entirely. Every design decision in this
document is filtered through one question:

> If the web application disappeared tomorrow, would the `contextshift`
> library still be useful to another developer or researcher?

If the answer is no, the code belongs in the application layer, not the
library.

## Layer diagram

```
Application            app.py, models.py, config.py — Flask, SQLAlchemy,
                        HTTP routing, persistence, the demo UI

      ↓ (imports)

Adapters                translates between application-specific types
                        (SQLAlchemy ORM rows) and library-neutral types
                        (contextshift.core.Message). Lives on the
                        application side of the boundary.

      ↓ (imports)

ContextShift Library    strategies/, tokenizers/, llm/, summarization/,
                        ingestion/ — the actual context-management logic,
                        zero web-framework dependency

      ↓ (imports)

Core Types              core/ — plain, dependency-free domain types
                        (Message, TokenBudget) that every other library
                        subpackage builds on
```

A machine-readable version of this diagram lives in
[`diagrams/layer-diagram.mmd`](diagrams/layer-diagram.mmd).

## Dependency rules

1. **Dependencies flow one direction only**, top to bottom in the diagram
   above. `contextshift/` never imports from `app.py`, `models.py`,
   `config.py`, or any adapter — the library must have zero awareness that
   a Flask application exists, let alone this one.
2. **`contextshift/` has zero dependency on Flask or SQLAlchemy**, or on
   any other application/web framework. Its only third-party dependencies
   are the ones a strategy or provider genuinely needs (e.g. an HTTP
   client for an LLM provider).
3. **Adapters are application-layer code**, not library code, precisely
   because an adapter's job is to know about *both* sides of the boundary
   (an ORM row and a `core.Message`) — code that knows about both sides
   cannot live inside the side that's supposed to know about neither.
   See [`decisions/0001-library-independence-and-adapter-placement.md`](decisions/0001-library-independence-and-adapter-placement.md).
4. **Within `contextshift/`, `core/` is the dependency sink.** Every other
   subpackage (`tokenizers/`, `strategies/`, `llm/`, `summarization/`,
   `ingestion/`) may depend on `core/`; `core/` depends on nothing else in
   the package. `summarization/` may depend on `llm/` (it needs a provider
   to call an LLM with). `strategies/` may depend on `tokenizers/` (it
   needs to measure token counts). No other cross-subpackage dependencies
   are expected; if one becomes necessary, it should be a deliberate,
   documented decision, not an incidental import.

## Architectural principles

These apply to every module added to `contextshift/` from the migration
onward:

- **Treat every new module as if it will eventually become a public API.**
  Public classes and functions carry type hints. Public modules carry a
  concise docstring stating their purpose. Implementation details that
  might need to change later are not exposed just because it's convenient
  today — a strategy's internal helper functions are not public API; its
  `ContextStrategy.build(...)` entry point is.
- **No premature API surface.** A module is not given exports, a class
  shape, or a documented contract before the code behind it actually
  exists — guessing at a public shape early just means breaking it later.
  (This is why the Step 1 scaffold ships empty subpackages with docstrings
  and no exports.)
- **Preserve behavior exactly during extraction.** While porting existing
  logic (`utils/token_manager.py`, `utils/context_builder.py`,
  `utils/summarizer.py`, `utils/file_processor.py`) into `contextshift/`,
  the goal is architectural separation, not improvement. Algorithms are
  not optimized, heuristics are not "fixed," and concepts are not renamed
  during a port — those are separate, deliberate decisions made later, not
  side effects of moving code.
- **Every migration step keeps the application runnable.** The old code
  path stays live until the explicit cutover step that replaces it;
  nothing is deleted until nothing depends on it.
- **Architecturally significant decisions are recorded**, not left
  implicit in code or conversation history. See [`decisions/`](decisions/).
