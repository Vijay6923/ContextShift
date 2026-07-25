# 0005 — Structural Protocols, not ABCs, for pluggable interfaces

## Status

Accepted. Formalizes a pattern already applied twice (`Tokenizer` in Step
3, `ContextStrategy` in Step 4) before it's applied a third time
(`LLMProvider`, Step 5).

## Context

Every pluggable interface in `contextshift/` so far has been implemented
as a `typing.Protocol` decorated with `@runtime_checkable`, rather than
an `abc.ABC` with abstract methods. The reasoning was written inline, in
full, in both `Tokenizer`'s and `ContextStrategy`'s docstrings --
duplicated rather than centralized, which is exactly the situation
`decisions/README.md` says should get an ADR instead: a decision that
constrains future work (every subsequent interface in this library) with
reasoning that, as written, lives only in code comments a reader would
need to find twice.

## Decision

Pluggable interfaces in `contextshift/` are structural `Protocol`s, not
`ABC`s, as a project-wide convention -- not re-litigated per interface.

Reasoning:

- **No inheritance requirement.** A third-party `Tokenizer` or
  `ContextStrategy` implementation satisfies the interface by having a
  method with the right name and shape. It never needs to import
  anything from `contextshift` to be usable by `contextshift` --
  relevant for a framework whose explicit goal is being useful to code
  that doesn't otherwise depend on it.
- **Nothing to share by inheritance, so nothing lost by not using it.**
  These interfaces are single-method behavioral contracts with no
  default implementation worth sharing across every conforming type. An
  ABC's main advantage over a Protocol -- shared base-class
  logic -- doesn't apply here.
- **`@runtime_checkable` gives `isinstance()` checks** (used by a future
  strategy/provider registry to validate a plugin) without requiring
  registration or inheritance.

**Known, accepted limitation:** `@runtime_checkable` Protocol
`isinstance()` checks verify method *names* are present, not that
signatures match. `isinstance(x, ContextStrategy)` returns `True` for any
object with a same-named `build` method, regardless of its parameters or
return type. There is no cheap way to get full signature verification
without giving up structural typing's actual benefit (no inheritance
requirement), so this is a deliberate tradeoff, not an oversight. A
future strategy/provider registry that needs stronger validation should
do so explicitly (e.g. a smoke-test call at registration time), not rely
on `isinstance` alone.

## Consequences

**Easier:** every future pluggable interface in this library (starting
with `LLMProvider` in Step 5) follows this convention by default, with
one citation instead of a fresh justification each time.

**Harder:** none identified relative to ABCs, given these interfaces
have no shared implementation to lose.

**Forecloses:** introducing an ABC-based interface anywhere in
`contextshift/` without a specific reason that overrides this default
(e.g. a future interface that genuinely needs shared base-class
behavior across implementations) -- and if that happens, it should
supersede this record, not silently diverge from it.
