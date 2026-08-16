---
name: Feature request
about: Propose a change that isn't a new ContextStrategy (see the New Strategy Proposal template for those)
title: ""
labels: enhancement
assignees: ""
---

## What's the concrete use case?

Describe what you're trying to do that the library doesn't currently
support — a real scenario, not a hypothetical one. See
[`docs/philosophy.md`](../../docs/philosophy.md)'s design principles:
a new field, method, or export is expected to trace back to a real,
existing consumer.

## Proposed change

What would you add or change? If it touches a public interface
(`ContextStrategy`, `Tokenizer`, `LLMProvider`, `VisionProvider`,
`ContextManager`), say which, and whether it's additive or breaking.

## Alternatives considered

What else could solve this, and why doesn't it fit as well? (Existing
strategies/tokenizers/providers you've already tried, if any.)

## Is this in scope for the library?

Check [`docs/philosophy.md`](../../docs/philosophy.md)'s "It
deliberately does not do" section first — vector databases/retrieval
infrastructure, agent/tool-calling orchestration, and prompt template
ownership are all explicitly out of scope. If your request touches one
of these, explain why this case is different.
