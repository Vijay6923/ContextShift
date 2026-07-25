# Architecture Decision Records

This directory records architecturally significant decisions made during
ContextShift's development — the ones that would otherwise live only in
conversation history and be invisible to the next person (including future
us) reading the code.

Not every choice needs a record here. A decision earns one when it meets at
least one of:

- it constrains future work (e.g. establishes a rule other code must follow),
- reversing it later would be costly,
- the reasoning behind it is non-obvious from reading the code alone.

## Format

Each record is a numbered Markdown file, `NNNN-short-title.md`, containing:

- **Status** — proposed / accepted / superseded (by which ADR, if so)
- **Context** — the situation and constraints that made a decision necessary
- **Decision** — what was decided, stated plainly
- **Consequences** — what this makes easier, what it makes harder, what it
  forecloses

Records are not edited after acceptance to reflect a changed decision —
a changed decision gets a new record that supersedes the old one, so the
history of *why* stays intact.

## Index

- [0001 — Library independence and adapter placement](0001-library-independence-and-adapter-placement.md)
- [0002 — Minimal public API surface pre-1.0](0002-minimal-public-api-surface.md)
- [0003 — Tokenizer scope excludes budget aggregation](0003-tokenizer-scope-excludes-aggregation.md)
- [0004 — The ContextStrategy interface](0004-context-strategy-interface.md)
- [0005 — Structural Protocols, not ABCs, for pluggable interfaces](0005-protocol-over-abc.md)
