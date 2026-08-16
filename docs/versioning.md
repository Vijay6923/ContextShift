# Versioning

ContextShift follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(`MAJOR.MINOR.PATCH`), with the additional pre-1.0 caveat semver itself
specifies:

> Major version zero (0.y.z) is for initial development. Anything MAY
> change at any time. The public API SHOULD NOT be considered stable.

## Where we are now

The current version is `0.1.0` — no release has shipped yet. Every
`0.x` release may include breaking changes to any public interface,
announced in [`CHANGELOG.md`](https://github.com/Vijay6923/ContextShift/blob/main/CHANGELOG.md) under that release's
heading rather than guaranteed in advance. This isn't a hedge — it's
accurate: [ADR 0002](decisions/0002-minimal-public-api-surface.md)
deliberately kept the public surface minimal specifically so that
internal restructuring pre-1.0 wouldn't also mean breaking an import
path nobody had a reason to rely on yet. A `0.x` user should pin an
exact version (`contextshift==0.1.0`) rather than a range, the same
practice any `0.x` dependency warrants.

## What counts as "the public API"

Everything importable from a subpackage's `__init__.py` (e.g.
`from contextshift.strategies import PinnedRecencyStrategy`) is public.
Anything reachable only through a private-looking path (a module without
an `__all__` entry, a name prefixed `_`) is not, regardless of whether
Python's import system happens to allow reaching it.

The four structural `Protocol`s — `ContextStrategy`, `Tokenizer`,
`LLMProvider`, `VisionProvider` (see
[ADR 0005](decisions/0005-protocol-over-abc.md)) — are the part of the
public API most worth being explicit about, since a third-party
implementation of one is exactly the kind of consumer a breaking change
would silently break without a type error to catch it:

- **`ContextStrategy.build(messages, budget) -> ContextResult`** — the
  method signature (parameter names, order, and the two-field
  `ContextResult` shape) is the contract. A new *optional* field on
  `ContextResult` is additive; changing what `messages`/`excluded`
  mean, or adding a required parameter to `build()`, is breaking.
- **`Tokenizer.estimate_tokens(text) -> int`** — likewise.
- **`LLMProvider.complete(messages, max_tokens) -> str`** and
  **`.stream(messages, max_tokens) -> Iterator[str]`**.
- **`VisionProvider.describe(image_bytes, mime_type, prompt=None) -> str`**.

A conforming third-party implementation of any of these needs no
dependency on `contextshift` itself (that's the point of a structural
`Protocol` over an `ABC`) — which also means this project cannot detect
at import time whether an external implementation still conforms after
a signature change. Changing one of these four signatures is treated as
a breaking (`MAJOR`, or any `0.x` bump pre-1.0) change for exactly this
reason, even though nothing would immediately fail to import.

## What `1.0.0` will mean

`1.0.0` is not a maturity or feature-completeness statement — it's a
commitment: from `1.0.0` onward, a `MINOR` release adds functionality
without breaking the four protocol signatures above or removing an
existing public export, and a `PATCH` release is a pure bug fix. That
commitment is being deferred deliberately, not by oversight — see
[ADR 0002](decisions/0002-minimal-public-api-surface.md) for why the
public surface stayed small in the first place, and
[`roadmap.md`](roadmap.md) for what's planned before it's made.
