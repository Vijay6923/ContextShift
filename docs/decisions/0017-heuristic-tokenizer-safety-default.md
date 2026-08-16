# 0017 — HeuristicTokenizer's safety default

## Status

Accepted.

## Context

[ADR 0014](0014-accurate-tokenizers.md) measured, rather than left
implied, `HeuristicTokenizer`'s real error rate: ~28% mean error
against a real tokenizer, worst case near 100% on a single input. That
number was published in the README and the ADR itself — but nothing
about *using* `HeuristicTokenizer` changed. It's still `ContextManager`'s
implicit default in every quick-start example, and every caller who
follows those examples inherits a documented ~28%-mean/~100%-worst-case
error rate on every budget decision without any signal, at the point
where it matters, that this tradeoff was made on their behalf. A
caller whose strategy "fits the budget" by the heuristic's count can,
in the worst case measured, actually be sending content that overflows
a real model's context window — a correctness risk with no runtime
signal pointing at its cause.

Two candidate fixes were considered:

**(a) Apply a conservative multiplier to budget calculations when
`HeuristicTokenizer` is in use** (e.g. `effective_budget = budget *
0.75`), so the *consequence* of the inaccuracy shrinks automatically.

**(b) Warn when `HeuristicTokenizer` is constructed**, pointing at
`TiktokenTokenizer` / `AnthropicTokenizer` as more accurate
alternatives, so the *caller* makes an informed choice instead of an
implicit one.

## Decision

**(b), a one-time `HeuristicTokenizerAccuracyWarning`, emitted from
`HeuristicTokenizer.__init__`** — implemented, not just chosen in the
abstract. (a) was rejected for a structural reason, not a
convenience one: nothing in this codebase would have a legitimate
place to *apply* that multiplier without violating a principle this
project has held since [ADR 0005](0005-protocol-over-abc.md) —
`Tokenizer` is a structural `Protocol` specifically so that
`ContextManager` and every strategy can depend on "something with an
`estimate_tokens()` method," never on which concrete implementation is
in play. Special-casing `HeuristicTokenizer` inside `ContextManager` —
`isinstance(tokenizer, HeuristicTokenizer)` triggering a hidden budget
adjustment — would reintroduce exactly the coupling the Protocol
design exists to prevent, and would be invisible to a caller passing a
duck-typed tokenizer that happens to have similar accuracy
characteristics (or worse ones) without being `HeuristicTokenizer`
itself. A budget multiplier also can't be justified by the measured
error's actual shape: ADR 0014's corpus shows both over- and
under-estimation depending on the input (a long repeated string
undercounts differently than a URL), so a single flat discount doesn't
target the actual failure mode — it would silently waste budget on
inputs the heuristic already estimates well, without reliably
protecting the inputs where it's furthest off.

**The warning is process-global (once per process), not per-call-site
(Python's own default `warnings` filter behavior) or per-instance.** A
module-level flag in `contextshift/tokenizers/heuristic.py`, reset by
tests via `monkeypatch`, guarantees exactly one warning regardless of
how many places in a caller's codebase construct a
`HeuristicTokenizer` — deliberately, not left to Python's default
per-`(message, category, module, lineno)` deduplication. This library
is constructed from many call sites across a typical application (this
repository's own test suite alone constructs one from 9+ different
files) — per-location deduplication would mean a caller sees this
warning repeated once per call site rather than once, training exactly
the "warnings are noise, ignore them" habit a warning exists to avoid.

**`HeuristicTokenizerAccuracyWarning` is exported from
`contextshift.tokenizers`**, so a caller who has deliberately chosen
this tradeoff can silence it explicitly —
`warnings.filterwarnings("ignore", category=HeuristicTokenizerAccuracyWarning)`
— rather than the warning being unfilterable or requiring a blanket
`-W ignore`.

## Consequences

**Easier:** a caller adopting ContextShift for the first time
(following the README's quick start, which uses `HeuristicTokenizer`)
sees, once, exactly the information ADR 0014 already measured and
published — not buried in documentation they'd have to go looking for.
Silencing it is one line, for a caller who has already made this
tradeoff deliberately (e.g. this repository's own example app,
`examples/flask-chat/`, which uses `HeuristicTokenizer` and does not
suppress the warning — it's meant to see it too).

**Harder:** none of `HeuristicTokenizer`'s actual budget-fitting
behavior changed. A caller who ignores the warning and never switches
tokenizers is exactly as exposed to the worst case ADR 0014 measured
as before this ADR — the warning is a visibility fix, not a
correctness fix. A caller who genuinely needs the correctness
guarantee should switch to `TiktokenTokenizer` or `AnthropicTokenizer`,
not rely on this warning alone.

**Forecloses:** treating `HeuristicTokenizer`'s inaccuracy as an
implicit, undocumented default going forward, the same way ADR 0014
already forecloses describing it vaguely. The two ADRs together mean
this tradeoff is now measured, published, and surfaced at the point a
caller actually makes it — not just written down somewhere they might
never read.
