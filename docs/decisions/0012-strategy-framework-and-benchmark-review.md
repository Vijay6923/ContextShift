# 0012 — Strategy framework and benchmark review

## Status

Proposed. This is a design review, not a decision — it exists to be
approved, amended, or rejected before any strategy-multiplicity or
benchmarking work begins. No code changes accompany this record.

## Context

ADR 0011 answered "what does ContextShift need to become a framework."
Phases 1–3 of that answer are built: `ContextManager` orchestrates a
strategy and a provider (Phase 1, cut over into the application in
Phase 2), and `contextshift.testing.FakeLLMProvider` is public (Phase
3). Phase 4 (Vision) is also built, as its own separate design/approval
cycle, extracting `contextshift.vision.VisionProvider` +
`GeminiVisionProvider` from a real, already-happened vendor swap.

This review asks a different question. The project's stated long-term
goal — recorded in `docs/architecture.md` since before ADR 0011 existed
— is "a framework for experimenting with and comparing LLM
context-window management strategies," not just an orchestration API.
Today, every pluggable interface in `contextshift/` (`Tokenizer`,
`ContextStrategy`, `LLMProvider`, `VisionProvider`) has exactly **one**
concrete implementation. The framework has never been exercised with a
second implementation of anything, and nothing in this repository has
ever measured, benchmarked, or compared a strategy against another. The
question this record answers: does the current architecture actually
support the stated long-term goal, and if pieces are missing, which
ones are justified to build now versus premature.

The governing rule is unchanged from ADR 0011, restated because
strategy multiplicity and benchmarking are exactly the areas most
likely to invite speculative architecture: **an abstraction earns its
existence only when there is a concrete consumer.** A stated long-term
*goal* ("should eventually support multiple strategies") is not, by
itself, a concrete consumer — every ADR in this repository that
rejected a registry, a Protocol, or a new field did so precisely
because "might be useful for a future X" was the only justification on
offer. This review holds itself to the same bar.

## Executive summary

The architecture already structurally supports everything this review
was asked about — proven, not assumed, by tests that exist today
(`test_duck_typed_class_satisfies_protocol_structurally` and its
analogues for every protocol in the repository). What's missing is not
design work; it's a second real data point for each interface, and a
reason to want one. Almost nothing reviewed below clears the
concrete-consumer bar for immediate implementation. The one substantive
gap is that the framework's "compare strategies" promise has never been
exercised even once — no second strategy, no comparison script, no
benchmark of any kind exists anywhere in this repository (confirmed by
searching the full tree). The recommended next step is smaller and more
conservative than "build strategy #2 and a benchmark suite": define one
concrete comparison question first, then build exactly the strategy and
the (external, non-framework) comparison capability that question
requires — together, driven by the question, not guessed at ahead of
it. This mirrors ADR 0007's Summarizer-Protocol deferral and ADR 0011's
own conclusion about evaluation ("you don't extract an interface from
zero implementations") applied one level up, to the framework's
research-toolkit ambitions as a whole.

## 1. Current state

**What ContextShift already supports**, read directly from
`contextshift/`:

- `core.Message` / `core.TokenBudget` — immutable, deliberately minimal
  domain types (no `id`, `timestamp`, or `is_archived`; ADR 0002).
- One `Tokenizer` (`HeuristicTokenizer`), behind a `@runtime_checkable`
  Protocol, with zero dependency on anything else in the package —
  `contextshift/tokenizers/__init__.py`: "no dependency on any other
  contextshift subpackage, including core."
- One `ContextStrategy` (`PinnedRecencyStrategy`), behind a Protocol,
  plus a shared `total_tokens()` helper.
- One `LLMProvider` (`GroqProvider`) — `complete()`/`stream()`, nothing
  vendor-specific in the interface (ADR 0006).
- One `VisionProvider` (`GeminiVisionProvider`) —
  `describe(image_bytes, mime_type, prompt=None)`, structurally
  narrower than `LLMProvider` (no history, no streaming), extracted
  from a real vendor swap (Groq → Gemini) rather than designed
  speculatively.
- `Summarizer` — one concrete implementation, deliberately *not* behind
  a Protocol yet (ADR 0007).
- `contextshift.ingestion` — PDF extraction and image preprocessing,
  pure functions, no AI/network dependency.
- `ContextManager` — orchestrates a strategy, a tokenizer, a budget,
  and a provider into `chat()`/`stream_chat()`, extracted from real
  duplication in `app.py`/`adapters.py`, not designed ahead of a
  consumer.
- `contextshift.testing.FakeLLMProvider` — the one deliberate exception
  to "consumer must be inside this repository," justified by "eval
  harness" and "external developer" being named target users in ADR
  0011's own charter.
- `adapters.py` (application-side, not in `contextshift/`) — the one
  place allowed to know about both ORM/Flask/`Config` and library
  types; every `build_X()` factory is constructed fresh per use to
  preserve "the app boots even without an API key."

**What is already extensible**, proven rather than claimed: every
interface is a structural `@runtime_checkable` Protocol (ADR 0005), and
every one has a test proving a hand-written, non-inheriting class
satisfies it —
`test_duck_typed_class_satisfies_protocol_structurally`
(`tests/test_strategies_base.py`), and the equivalent conformance tests
in `tests/test_llm_base.py`, `tests/test_tokenizers.py`,
`tests/test_vision_base.py`. This means a second implementation of any
of these four interfaces requires **zero changes** to `ContextManager`,
to any existing strategy/provider/tokenizer, or to the application —
not a design aspiration, an already-demonstrated property.

**What is intentionally minimal**, by direct citation:

- No registry anywhere. `contextshift/strategies/__init__.py`: "There
  is no registry for looking up strategies by name yet: with one
  strategy in existence, a registry has nothing to register."
- No `Summarizer` Protocol (ADR 0007 — deferred until a second
  approach exists to design one against).
- No system-prompt ownership anywhere in the library — independently
  arrived at four separate times (ADR 0004 for strategies, ADR 0006
  for providers, ADR 0007 for summarization, ADR 0011 for
  `ContextManager`'s `system_prompt` staying caller-supplied).
- `contextshift/__init__.py` re-exports exactly one name
  (`ContextManager`); everything else is imported from its owning
  subpackage (ADR 0002, ADR 0011 §2).

**Architectural principles consistently followed**, patterns visible
across ADR 0001–0011 read together, not any single one:

1. **Concrete-consumer discipline.** The single most repeated
   sentence in this repository's history, in one phrasing or another,
   across ADR 0002 (`Message.timestamp`), ADR 0004
   (`ContextResult`'s excluded-reasons trace), ADR 0006 (`temperature`
   as an internal constant, not a parameter), ADR 0007 (no `Summarizer`
   Protocol), and ADR 0011 (`testing.py`'s justification, the
   "DO NOT IMPLEMENT" list for Phase 1).
2. **One-directional dependencies**, enforced twice: Application →
   Adapters → Library → Core at the outer level, and inside the
   library, `core/` is the dependency sink (`tokenizers/` depends on
   nothing, `strategies/` depends on `core/` only, `summarization/`
   depends on `llm/`'s Protocol only) — `docs/architecture.md`'s
   Dependency Rule 4, verified by the actual import graph, not just
   asserted.
3. **Protocol over ABC**, project-wide (ADR 0005), applied to every
   pluggable interface without exception, including the two newest
   (`VisionProvider`, and `ContextManager`'s dependencies).
4. **Small, single-purpose interfaces.** `Tokenizer` and
   `ContextStrategy` each have one method; `LLMProvider` has two;
   `VisionProvider` has one. None grew a second capability without a
   concrete need forcing it.
5. **Inspectability over convenience.** `ContextResult.messages` /
   `.excluded`, `ChatResult.context` / `.user_message` — every result
   type exposes what happened, not just an opaque final answer. This
   is a *design requirement*, stated explicitly in ADR 0004, not an
   incidental nicety, and it is exactly what makes Q4/Q5 below
   answerable without new framework code.
6. **Application framing stays outside the library, always.** Prompt
   text, `"[SUMMARY]"` labels, response truncation, persistence,
   token-usage JSON shapes — every one of these was independently
   pushed to the application side (ADR 0003's `get_token_stats`
   reasoning, ADR 0004, ADR 0006, ADR 0007, ADR 0011's Non-goals).
7. **Characterization testing at every extraction.** Every port in
   this project's history (Steps 3–8, Vision) was verified by a direct
   old-vs-new comparison over real scenarios, not just independent
   unit coverage — the discipline this review's own conclusions lean
   on in §4/§5 below (the framework is already inspectable enough to
   benchmark *because* this discipline demanded it be).

## 2. Multiple context strategies

**Should ContextShift support multiple strategies, structurally?**
It already does — §1 above is the evidence, not a projection. The real
question this section answers is which *implementations* are justified
now, using the same test applied everywhere else in this repository:
does something concrete need it.

- **Sliding Window** (keep the last *N* messages by count, no budget,
  no pinning). Genuinely different from `PinnedRecencyStrategy`, which
  is budget-driven and recency-*protected*, not count-driven. **Solves
  a real, narrow problem**: predictable memory/latency regardless of
  token variance. **Implementable with existing abstractions,
  entirely** — `ContextStrategy.build(messages, budget) -> ContextResult`
  is already sufficient; a sliding window is a new class, not a new
  interface. **Requires no new abstractions.** **Current consumer:
  none** — nothing in `app.py`/`adapters.py` needs one, and no
  benchmark exists to compare it against `PinnedRecencyStrategy`. This
  is the cheapest strategy to build whenever a real trigger appears
  (see §10), but there isn't one today.
- **Recency** (plain, no pinning). Not a new strategy at all —
  `PinnedRecencyStrategy` with no message ever pinned already *is*
  this. No abstraction gap, nothing to build.
- **Pinned Recency.** Already exists; the production strategy.
- **Hybrid.** Answered in §3 — if built, a self-contained class, not a
  new composability primitive.
- **Semantic Retrieval.** Solves a real problem conceptually (finding
  relevant *old* messages beyond a fixed recency window), but
  **requires a new abstraction that does not exist**: an embedding
  capability. `LLMProvider` explicitly excludes embeddings (ADR 0006's
  "Forecloses" clause), and no embedding code exists anywhere in this
  repository to extract an interface from. **Should not exist yet** —
  no concrete consumer, and building the interface now would repeat
  the exact mistake ADR 0008 named and avoided for vision before
  Gemini existed: designing an abstraction from zero implementations.
- **Hierarchical Memory.** Maps directly onto ADR 0011's already-
  rejected "memory/sessions" non-goal ("no concrete consumer needs
  framework-owned persistence"). `Summarizer` already exists and could
  be *used* by an application to build a compressed system message
  that a strategy then pins — that composition is possible today with
  zero new code. A genuine multi-tier memory system is a different,
  much larger thing with no consumer. **Should not exist yet.**

**What should stay application-specific:** which strategy a given
conversation actually uses (a configuration/routing decision, not a
library concern — exactly how `adapters.build_strategy()` already
works), and any strategy whose selection signal is UI-specific (e.g.
"importance" derived from user actions the app tracks) — that signal
gets translated into `Message.is_pinned` or an equivalent field by the
adapter layer, the same boundary `to_core_message()` already draws.

**Which should not exist yet:** Semantic Retrieval (no embedding
capability), Hierarchical Memory (persistence non-goal, ADR 0011),
Hybrid as a *generic* composition primitive (§3). Sliding Window is
architecturally free to build at any time but has no current
consumer — it is the leading candidate *when* one appears (§10), not a
recommendation to build it now.

## 3. Strategy composition

**Should strategies be composable via a generic, exposed mechanism?**
No. **Should `Hybrid` simply combine existing strategies?** If one is
ever built, yes — as its own concrete `ContextStrategy` implementation
that composes by delegation (e.g. constructor-injected sub-strategies
whose results it merges however its own policy dictates), not as a
new framework-level composability primitive. **Should ContextShift
expose a `StrategyPipeline`?** No — and this is not a close call.

The evidence: `contextshift/strategies/base.py`'s
`ContextStrategy.build(messages, budget) -> ContextResult` is already
sufficient plumbing for internal composition. A `HybridStrategy` can
call `self._strategy_a.build(...)` and `self._strategy_b.build(...)`
inside its own `build()` and merge the two `ContextResult`s however it
wants — no interface change required, because `build()` doesn't care
whether its own logic delegates to other objects or not. This is the
same reasoning as ADR 0007's Summarizer-Protocol deferral, one level
up: designing a *generic* composition shape (union candidates? vote?
weight? sequential filtering?) now would mean guessing at what
"combining strategies" even means, with exactly zero real hybrid
implementations to validate the guess against — worse odds than ADR
0007 faced, which at least had one real summarization approach to
generalize from eventually. ADR 0011 already named this exact idea and
rejected it directly: `pipeline/` — "No concrete consumer assembles a
dynamic multi-step chain; the one real orchestration need is
fixed-shape." Nothing has changed since that was written.

## 4. Benchmarking

**Does benchmarking belong inside `contextshift/`?** Mostly no, and
ADR 0011 already reached most of this conclusion under a different
question ("is an evaluation harness missing"): "Nothing in this
repository has ever computed a metric or scored a strategy. Per this
project's own rule, you don't extract an interface from zero
implementations. An eval harness should be a separate project
*depending on* `contextshift`, not a subpackage built speculatively
inside it." This review's contribution is the metric-by-metric
breakdown that ADR 0011 didn't need to do:

| Metric | Needs new framework code? | Where it belongs |
|---|---|---|
| Token usage | **No** — `total_tokens()` and `Message.token_count` already exist | Nothing to build; already public |
| Messages retained | **No** — `len(ContextResult.messages)` | Nothing to build; already public |
| Messages discarded | **No** — `len(ContextResult.excluded)` | Nothing to build; already public |
| Selection latency | **No** — `time.perf_counter()` around any `strategy.build(...)` call | Caller's job; not a framework concern, same category as "the caller decides whether to log" |
| LLM latency | **No** — same, around `provider.complete()`/`.stream()` | Caller's job |
| Overall latency | **No** — sum of the above | Caller's job |
| Provider cost | Requires external pricing data (per-model, changes over time) | External infrastructure / application-side; `LLMProvider` was deliberately scoped to `complete`/`stream` only (ADR 0006), nothing about cost |
| Quality / answer similarity | Requires a judge, reference answers, or embeddings — none exist here | External infrastructure; a separate eval project (ADR 0011 §1) |
| Memory efficiency | Ambiguous: if "context size," identical to token usage above; if "process footprint," an orthogonal systems concern | Not this project's concern either way |

The load-bearing finding: **the framework doesn't need a benchmark
module to be benchmarkable — it already is**, because `ContextResult`
is transparent by design (ADR 0004's entire point) and `total_tokens`
is already public. This is the same principle that made
`ContextManager`'s `ChatResult` deliberately "not reduced to a bare
string" (ADR 0011 §2) — transparency was built in specifically so a
caller or harness could inspect a result, without the framework ever
needing to define what "benchmarking" means.

## 5. Research toolkit

**Can ContextShift evolve into a research toolkit?** Yes — it is
already the project's stated charter (`docs/architecture.md`'s opening
paragraph). But "evolve into a research toolkit" does not mean
"`contextshift/` needs a `benchmark/` subpackage." **Minimum useful
benchmark architecture**, given §4's finding: an external script (in
`examples/`, or a genuinely separate small tool, not `contextshift/`)
that constructs two or more `ContextStrategy` instances, runs them over
a fixed set of `Message` sequences, and reports the `ContextResult`
stats each already exposes, side by side. This needs zero new
`contextshift/` code *once a second strategy exists* — the transparency
work is already done.

**Should users be able to compare strategies?** Yes, and they already
can, mechanically, today — call `.build()` on N strategy instances
against the same input, compare the two `ContextResult`s. What's
missing is not capability, it's a second strategy to compare against
(§2) and a script demonstrating the pattern.

**Should reports be generated?** Not by the framework. Report
formatting/dashboards is presentation — the exact category ADR 0003
already pushed out of `tokenizers/` (`get_token_stats`'s JSON shape was
named as "a strong candidate for staying application-side entirely").

**Should datasets belong inside the framework?** No — ADR 0011 §1
already answered this directly: eval-harness content (synthetic
conversations with planted facts, mentioned in `docs/roadmap.md`'s V3
entry) belongs in a separate project, not `contextshift/`.

**Should evaluation stay external?** Yes, consistent with the above
and with `docs/roadmap.md`'s own framing, which lists "a reproducible
benchmark suite... a results dashboard" as a distinct future milestone
(V3/"Research version"), never as `contextshift/` subpackage work.

## 6. Pythonic API

`from contextshift import ContextManager; manager = ContextManager(...)`
— **this already exists, exactly as written**, and already aligns with
everything built: `contextshift/manager.py` + the one top-level
re-export (ADR 0011 §2). `ContextManager`'s constructor already takes
`strategy`, `provider`, `tokenizer`, and `budget` as plain objects —
dependency injection, not string or registry lookup.

**Selectable by object?** Already true today — that *is* the
constructor signature, and is the primary, already-working selection
mechanism. Nothing needs to change.

**By registry?** Rejected, repeatedly, and explicitly, at a bar this
review doesn't even reach: `contextshift/strategies/__init__.py`
itself: "a registry has nothing to register" with one strategy in
existence. ADR 0011 §3 went further, rejecting `registry/` even for
the case of *multiple* implementations existing: "Trigger: A second
concrete strategy or provider implementation actually lands" — and per
§2 above, that trigger hasn't fired yet either. Registry-by-name is
premature twice over right now.

**By string?** A special case of "by registry" (a string can't select
anything without something mapping strings to classes) — same
rejection, same reasoning.

**Should this be deferred?** Yes, unambiguously, on the same grounds
every registry-flavored idea in this project has been rejected on
since Step 4.

## 7. Tokenizer plugins

**Do they belong in the framework?** The interface already supports
them, structurally, with no changes needed. `contextshift/tokenizers/base.py`'s
own docstring: "A future tiktoken-backed tokenizer, or a
provider-native tokenizer that calls a vendor's counting endpoint,
satisfies this interface simply by having a matching `estimate_tokens`
method" — `estimate_tokens(text: str) -> int` has zero dependency on
vendor, message shape, or anything else in the package. This is the
same "capability over vendor" test ADR 0006 applied to `LLMProvider`,
already true here without any new decision needed.

**Should the `Tokenizer` interface change?** No — "which vendor
counts the tokens" doesn't change the shape of "text in, int out."

**Should nothing change?** Correct, for the interface. What's missing
is concrete implementations, which is low-risk, purely additive work
whenever it happens — but per the same consumer test as §2:
`HeuristicTokenizer` is used everywhere today, and nothing currently
needs exact counts (it was named "heuristic" from the start
specifically because the application's own budget math tolerates
approximation, ADR 0003). This is the *closest* candidate to having a
real justification among everything reviewed here — accuracy under a
tight budget is a genuinely different property than heuristic
word-counting provides — but it has not been triggered by anything
concrete yet, and should wait for one (see §10's Phase C).

## 8. Provider expansion

**Does the current `LLMProvider` interface already support OpenAI,
Anthropic, Ollama?** Yes, unambiguously. `LLMProvider` is
`complete(messages, max_tokens=1024) -> str` +
`stream(...) -> Iterator[str]`, deliberately vendor-neutral (ADR
0006: "nothing in this interface mentions Groq, OpenAI, or any
specific wire format"). `GroqProvider` is the proof: it owns 100% of
its own auth, wire format, and retry/backoff internally, exposing none
of it through the interface. ADR 0006's own Consequences section
predicted exactly this: "a second provider... is a new class
implementing two methods against plain `Message` objects, with zero
changes to any strategy or to `contextshift.summarization`." A local
model (Ollama) doesn't change this either — nothing in `complete()`/
`stream()`'s signature assumes HTTP versus in-process inference, the
same conclusion ADR 0010 §4 already reached for a hypothetical local
*vision* model.

**What would actually require changes?** Nothing in the interface.
Each new provider needs its own wire-format/auth/retry implementation
(comparable to `GroqProvider`'s ~160 lines) — engineering work, not
interface-design work.

**What should explicitly not be built yet?** The concrete provider
classes themselves. Unlike vision (where a real vendor swap, Groq →
Gemini, already happened and directly motivated `VisionProvider`),
**no text `LLMProvider` has ever been swapped in this project** — Groq
has been the only chat provider since Step 5. Building a second one
now would be exactly "designing for hypothetical future users," not
extracting from a real need. Also not warranted: a provider registry
or factory-of-providers (same rejection as §6), and no shared base
class for "REST-based providers" — one data point (`GroqProvider`) is
not enough to generalize a shared implementation from, the same
reasoning ADR 0005 already gives for why Protocols, not ABCs, are used
throughout ("nothing to share by inheritance... these interfaces have
no shared implementation to lose").

## 9. Vector stores

**Should vector databases (FAISS, Chroma, Qdrant, Pinecone) belong
inside ContextShift?** No — and this repository has already said so.
ADR 0011's Non-goals section lists "vector stores" explicitly under
*permanent, structural* non-goals, alongside databases and HTTP
servers, on the grounds that owning one would contradict
`docs/architecture.md`'s own governing question ("if the web
application disappeared tomorrow, would `contextshift` still be
useful to another developer?") — a library that owns a specific vector
database binding is useful only to whoever chose that database.

**Should ContextShift own retrieval, or only context selection?**
Only selection — this distinction is already load-bearing throughout
the architecture. `ContextStrategy.build(messages, budget)` operates
on an *already-assembled* candidate list; it selects among what it's
given, it does not fetch anything. This mirrors how
`contextshift.ingestion` owns extraction, not storage, and how
`contextshift.llm` owns the model call, not conversation persistence.
A semantic-retrieval strategy, if built, would still just be handed a
candidate list — by whatever external system did the retrieving — and
decide what fits the budget, same as every strategy today.

**Does this require a Retrieval interface?** Not yet. No retrieval
code — no embeddings, no vector math, no external DB client — exists
anywhere in this repository to extract an interface from. Designing
one now would repeat the exact "zero implementations" mistake ADR
0011 §1 already named for evaluation and ADR 0007 already avoided for
`Summarizer`.

**Is this premature?** Yes, doubly so — it's downstream of Semantic
Retrieval (§2), which is itself gated behind an embedding capability
that doesn't exist and has no trigger.

## 10. Roadmap

Every phase below is scoped smaller than "build a second strategy and
a benchmark suite," deliberately, because that framing is exactly what
this review's self-challenge (§11) found the least defensible
recommendation on offer.

**Phase A — Define one concrete comparison question.** Not code. The
prerequisite everything else in this review depends on, and the one
thing genuinely missing today: a specific, falsifiable question (e.g.
"does pinned-recency retain more relevant context than count-based
sliding-window truncation, at equal token cost, over realistic
conversation lengths") that names which second strategy is actually
needed and what "compare" needs to measure. Concrete consumer: every
recommendation in §2–§9 that this review declined to approve is
declined specifically because no such question exists yet to justify
it — this phase is what would change that.

**Phase B — Build exactly what Phase A's question requires, together.**
The second `ContextStrategy` implementation Phase A named (sliding
window is the cheapest default candidate per §2, but the actual choice
belongs to the question, not this review), plus a minimal *external*
comparison script (`examples/`-shaped, not a `contextshift/`
subpackage, per §5 and ADR 0011 §1's "separate project" conclusion)
that runs both strategies over fixed `Message` fixtures and reports
`ContextResult`-derived stats — using what `contextshift/` already
exposes today, adding nothing to the library itself beyond the one new
strategy class.

**Phase C — Whatever Phase B's real run concretely surfaces as
missing.** Not pre-specified, deliberately. If `HeuristicTokenizer`'s
approximation turns out to distort the comparison, that is the trigger
for a real tokenizer (§7). If a second provider becomes genuinely
necessary (e.g. to rule out provider-specific behavior as a
confound), that is the trigger for §8. If real captured conversations
from the live application are needed rather than synthetic fixtures,
*that* is the trigger for `docs/roadmap.md`'s "Priority note" on
conversation/session isolation — not before, and not as a
`contextshift/` concern even then (it's an application/eval-harness
concern, since `Message` deliberately carries no session identity, ADR
0002).

**Phase D — Not scheduled, no trigger exists today.** Semantic
retrieval, an embedding interface, a `Retriever` interface, vector
store integration, a second production-grade `LLMProvider`, any kind
of registry (strategy, provider, or config), a `StrategyPipeline`. Each
is gated behind something Phase A/B/C would need to concretely surface
first.

## 11. Self challenge

The sharpest challenge to this entire review: **the framework has
operated correctly with exactly one strategy, one tokenizer, one
text provider, and one vision provider for its entire existence.
Why does anything need to change now, just because this review was
asked for?** The honest answer is that it doesn't, yet. The request
that triggered this review states a *long-term goal*
("eventually... multiple strategies... benchmarking... research"),
and per this project's own standing rule, a goal is not a concrete
consumer — the same distinction ADR 0002 drew between "a future
strategy might need this" (rejected) and "this strategy needs this"
(accepted).

Applying that same challenge to every recommendation above:

- Is Sliding Window solving an existing problem? No — nothing calls
  for it today. It's cheap and low-risk *whenever* a real trigger
  appears, which is different from recommending it now.
- Is "define a comparison question" (Phase A) itself premature? This
  was checked hardest, because it's the review's own recommendation.
  It survives the challenge because it is not code, not an API
  addition, and not a commitment to any specific strategy shape — it
  is the same kind of question-first discipline ADR 0007 already
  applied to `Summarizer` and ADR 0011 §1 already applied to
  evaluation, generalized to "before building strategy #2 at all."
  Recommending *nothing at all*, full stop, was seriously considered
  as more defensible than Phase A — rejected only because the
  project's own stated charter (`docs/architecture.md`'s opening
  paragraph) makes "eventually compare strategies" an explicit,
  already-recorded goal, not a speculative one this review invented.
- Is the metrics table in §4 solving a real problem? Yes, directly —
  it answers "what would we even measure" without adding a single line
  of code, which is the correct amount of investment for a question
  with no current implementation to build against.

## 12. Non-goals

Explicitly not to be implemented now, with why each waits:

- **Strategy registry / provider registry / config-driven selection
  by string.** Rejected at a bar this review doesn't reach — even
  ADR 0011 §3's own trigger ("a second concrete strategy or provider
  lands") hasn't fired. Wait for: two or more real implementations of
  the same interface, in production use, where choosing between them
  by string is a real, recurring operation — not just existing.
- **Plugin discovery.** Structural Protocols already deliver "plug in
  your own X" with no discovery mechanism needed (ADR 0005, ADR 0011
  §8). No third-party ecosystem exists to discover from.
- **Session/conversation isolation as a `contextshift/` concept.**
  `Message` deliberately carries no identity (ADR 0002). When needed,
  it's an application or eval-harness concern. Wait for: Phase C
  concretely needing real captured conversations, not synthetic
  fixtures.
- **Memory/hierarchical-memory abstraction.** Already rejected in ADR
  0011's Non-goals ("no concrete consumer needs framework-owned
  persistence"); nothing here changes that.
- **Dataset system.** Eval-harness-shaped content; explicitly a
  separate-project concern per ADR 0011 §1.
- **Evaluation framework / benchmark subpackage inside
  `contextshift/`.** Same citation — "you don't extract an interface
  from zero implementations." §4/§5 show the framework doesn't need
  one to be benchmarkable regardless.
- **Telemetry / events.** Already rejected in ADR 0011 §8;
  transparency (`ContextResult`, `ChatResult`) substitutes for it.
  Wait for: a consumer needing to observe *inside* a call, not just
  its result — still not the case.
- **Configuration hierarchy.** Constructor kwargs already work (ADR
  0011 §6). Wait for: a consumer needing to instantiate from a file or
  string (e.g. a CLI flag) — narrow and concrete when it happens, not
  a general system.
- **Composite/generic `StrategyPipeline`.** No second-plus-third
  strategy to design a composition shape against (§3). Wait for: a
  real `HybridStrategy` implementation revealing what "combining"
  actually needs to mean — and even then, likely stays one concrete
  class, not a new primitive.
- **Embedding interface / `Retriever` interface / vector store
  integration.** Zero implementations to extract an interface from
  (§9); gated behind Semantic Retrieval (§2), itself gated behind a
  real research question (§10 Phase A).
- **A second, production `LLMProvider` implementation.** Interface
  already supports it (§8); no vendor swap has ever happened for text,
  unlike vision. Wait for: a concrete need (cost, latency, capability)
  that Groq doesn't meet, surfaced by real use — not "frameworks
  usually support multiple providers."
- **Tokenizer plugins as actual implementations.** Interface already
  supports them (§7); `HeuristicTokenizer` has never blocked anything.
  Wait for: Phase C concretely showing the heuristic distorts a real
  comparison.
- **Provider cost tracking, pricing tables.** External data with no
  reason to live in a library scoped to `complete`/`stream` (ADR
  0006). Application or eval-harness concern if it ever matters.
- **Quality/answer-similarity scoring.** Requires judge/reference/
  embedding infrastructure that doesn't exist; separate eval project
  per ADR 0011 §1.
- **Report generation, dashboards.** Presentation; always
  application-side per ADR 0003's precedent.

## 13. Final recommendation

**What should be built next:** Nothing in `contextshift/` code,
immediately. The concrete next step is Phase A (§10) — naming one real
comparison question — which is scoping work, not implementation, and
is explicitly excluded from this review's own deliverable per the
instructions that requested it.

**What should not be built:** Any registry (strategy, provider, or
config), a `StrategyPipeline`, an embedding or `Retriever` interface,
vector-store integration, a benchmark/evaluation subpackage inside
`contextshift/`, a dataset system, telemetry/events, a session/memory
abstraction, or a second strategy/tokenizer/provider implementation
built ahead of a real trigger. All are listed in §12 with what would
need to be true before each becomes justified.

**Confidence:** **High** that the current architecture already
structurally supports everything asked about in this review — this is
demonstrated by existing tests, not projected. **Medium-high** that
"define the question before writing code" (Phase A) is the right next
step: it is consistent with every precedent in this repository (ADR
0007, ADR 0011 §1) but is an unusual recommendation in that it isn't
code, and a reader hoping for "build strategy #2 now" may reasonably
push back on it. **Low-to-medium** on which strategy, tokenizer, or
provider Phase B actually ends up building, since that is explicitly
left to evidence this review doesn't yet have.

**Known uncertainties:** whether "research" in the request that
triggered this review means an internal, informal exercise (one
comparison script, good enough for internal use) or something aiming
at a citable, reproducible public result (which would raise the bar on
dataset size, methodology, and statistical rigor considerably). This
materially changes how much Phase B should invest, and isn't
answerable from the repository alone — it's a scope decision for
whoever owns Phase A's question.

**Risk of overengineering:** **High** if Phase A and B are skipped and
work jumps straight to registries, a generic pipeline, vector-store
integration, or a benchmark subpackage designed before any real
comparison has ever been run. That would repeat, at much larger scale,
the exact mistake ADR 0002 corrected for `Message.timestamp` and ADR
0007 avoided for `Summarizer`: designing an abstraction's shape before
a real second data point exists to design it *from*. The single
highest-leverage discipline this record can offer is procedural, not
architectural: let Phase A's question generate Phase B's actual
required shape, rather than guessing at a research toolkit's
architecture in advance of ever using one.

## Consequences

**Easier:** the next time strategy multiplicity or benchmarking work
is proposed, it starts from an explicit account of what's already
proven (duck-typed conformance, §1), what's genuinely missing (a
second data point, not a design), and a metric-by-metric answer to
"what would benchmarking even need" (§4) — instead of re-litigating
questions this record already worked through.

**Harder:** none introduced — this record adds no code and changes
nothing about the current system, matching ADR 0010's own framing for
the same kind of analysis-only record.

**Forecloses:** treating "the project's long-term goal mentions X" as
sufficient justification for building X now. Every non-goal in §12
names the specific, concrete condition that would flip it to yes — the
same discipline ADR 0002 established for `Message` fields, applied
here to an entire class of future framework surface at once.
