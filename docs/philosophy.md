# Philosophy

## What is ContextShift?

Every multi-turn LLM application eventually faces the same problem: the
conversation grows past what's worth sending to a model on every turn,
whether because it exceeds the context window outright or because
sending irrelevant history wastes tokens, latency, and money on content
that doesn't matter to the current turn. Cost and latency scale with
tokens sent, regardless of whether those tokens are relevant.

The usual response is ad hoc: truncate the oldest messages, summarize
occasionally, or simply rely on the model's context window and hope it's
large enough. This logic is typically implemented once, inline, tangled
up with whatever web framework and database the application happens to
use — which makes it untestable in isolation and impossible to compare
against an alternative.

A larger context window does not solve this. It only delays the point at
which a deliberate policy becomes necessary, at increasing cost per turn.
ContextShift exists to make that policy explicit: a **strategy** decides
which messages belong in context under a token budget; a **provider**
decides how to actually talk to a model; a **manager** composes the two
into a single call. Each piece is a small, swappable interface, testable
without a network connection, and independently comparable via a
built-in benchmark.

**Who this is for:** anyone building a multi-turn LLM application (a
chat product, a CLI assistant, an agent) who needs an explicit, testable
policy for what a model sees each turn — and anyone comparing
context-management strategies against each other, since that comparison
is a first-class, built-in capability rather than something to build
from scratch.

## Scope

ContextShift focuses on three things:

- **Context selection** — deciding which messages fit a token budget.
- **Orchestration** — composing a strategy and a provider into one call.
- **Benchmarking** — comparing strategies on measurable properties,
  including whether a strategy actually preserved what a later question
  depends on (see [needle-retention benchmarking](decisions/0013-needle-retention-benchmark.md)),
  not just how it's configured.

It deliberately does not do:

- **Vector databases or retrieval infrastructure.** ContextShift selects
  from a candidate list it's given; it doesn't fetch that list from
  anywhere. A strategy backed by retrieval is expressible on top of this
  library, but owning a specific vector store binding would only be
  useful to whoever chose that store.
- **Agent frameworks or tool-calling orchestration.** A different
  capability, with a different consumer, than deciding what a model
  sees.
- **Prompt engineering or prompt template management.** What a system
  prompt says is an application's decision, not the library's — every
  interface in ContextShift (strategies, providers, the manager) is
  scoped to *where* prompt framing goes, never *what* it says.

## Design principles

- **A field, method, or export exists because something concretely
  needs it**, not because it might be useful someday. Every abstraction
  in this codebase traces back to a real, existing consumer.
- **Interfaces are structural `Protocol`s, not `ABC`s.** A `Tokenizer`,
  a `ContextStrategy`, an `LLMProvider`, a `VisionProvider` is defined
  entirely by having a matching method. A conforming implementation
  needs no dependency on ContextShift itself.
- **Dependencies flow one direction only.** The library never imports
  from the example application; within the library, core types depend
  on nothing, and every other subpackage depends only on what its job
  actually requires.
- **Every decision is inspectable.** A strategy's result exposes what
  it kept and what it excluded; nothing is hidden inside a side effect.
- **No framework-owned persistence.** ContextShift has no database,
  no session concept, and no memory abstraction — an application or
  eval harness owns storage; the library owns the selection policy.
- **A benchmark claim is backed by a measured number, not an implied
  one.** If a metric follows directly from a strategy's own
  configuration (e.g. "kept exactly `window_size` messages"), it isn't
  evidence the strategy is *good* — see
  [ADR 0013](decisions/0013-needle-retention-benchmark.md) for what
  changed once this was taken seriously.

The full reasoning behind each of these is recorded in
[`decisions/`](decisions/) as they were decided, not reconstructed after
the fact.
