# 0011 — Framework v2 design review

## Status

Proposed. This is a design review, not a decision — it exists to be
approved, amended, or rejected before any Framework v2 implementation
phase begins. No code changes accompany this record.

## Context

The migration (ADRs 0001–0010) produced a library — `contextshift/` has
no Flask dependency, its interfaces are structural Protocols, and every
piece was extracted from one real, working implementation. But "a
library extracted from one application" and "a general-purpose framework"
are different products. The stated goal now is the second one: someone
should be able to `pip install contextshift` and build a chatbot, a CLI
assistant, a RAG system, or an eval harness against it — never having
seen this repository's Flask app.

This review answers the ten questions posed, in order. The governing
rule throughout, restated because it's the thing most likely to get
violated under the pressure of "make this feel like a framework": **an
abstraction earns its existence only when there is a concrete consumer.**
Every "yes, build this" below names one. Every "no, not yet" names the
condition that would flip it to yes.

## Executive summary

The framework is closer to done than the question list implies. Of the
ten areas reviewed, one has a real, load-bearing gap with a concrete
consumer sitting in this repository right now. The rest are either
already solved (verified, not assumed) or correctly not-yet-buildable
because nothing concrete needs them yet.

**The one real gap: orchestration.** `adapters.py::build_chat_context`
and the Flask `/chat` route hand-assemble "run a strategy, prepend a
system prompt, call a provider, wrap the reply" every time — that
sequence has never been extracted into something reusable, because
until now there was only one caller. A framework needs that sequence to
be a public, composable object, not fifteen lines a Flask route
happens to get right. That's `ContextManager` (name open for debate).
Almost everything else on the question list — registries, config
objects, sessions, plugins, composite strategies, a growable Provider
interface — has no concrete consumer today and should stay unbuilt,
for the same reason `Message.timestamp` stayed unbuilt in ADR 0002.

## 1. What is missing for ContextShift to become a framework?

Going through each named use case concretely, not abstractly:

| Use case | What's already there | What's actually missing |
|---|---|---|
| **Chatbot** | Strategy, Provider, Tokenizer, Summarizer — everything except orchestration | Orchestration (§2). Persistence is *not* missing — it's correctly the caller's job, same as today's Flask app |
| **CLI assistant** | Same as chatbot | Same as chatbot — this is the closest-to-ready use case once orchestration exists, since a CLI naturally owns its own history (a list, or a JSON file) with no database needed |
| **Coding assistant** | Same building blocks | Tool calling. Real gap, correctly out of scope (no concrete implementation anywhere in this repo to extract an interface from — see §5) |
| **Agent** | Same building blocks, composable via repeated orchestrator calls | Tool calling (same gap). A "scratchpad" or planning-memory concept — genuinely open, no concrete consumer, not addressed here |
| **RAG system** | Strategy *interface* already supports a retrieval-based implementation without any framework change | Embeddings (real gap, §5). A concrete semantic-retrieval `ContextStrategy` (not a framework gap — the extensibility already exists; nobody has built one) |
| **Evaluation harness** | Strategy/Provider/Tokenizer already fake-able and composable | A *public* fake provider (§3, §8) — today's `FakeLLMProvider` is test-only by deliberate design (ADR 0006), and "eval harness" is now a named target user, not a hypothetical one |

**Not missing, contrary to how the question is sometimes framed:**
metrics, datasets, and scoring logic for an eval harness. Nothing in
this repository has ever computed a metric or scored a strategy. Per
this project's own rule, you don't extract an interface from zero
implementations. An eval harness should be a separate project
*depending on* `contextshift`, not a subpackage built speculatively
inside it (§3 goes further into why `evaluation/` specifically should
not exist yet).

## 2. Public API

### The central recommendation: one orchestration entry point

```
ContextManager(strategy: ContextStrategy, provider: LLMProvider, budget: TokenBudget, tokenizer: Tokenizer | None = None)
    .chat(history: Sequence[Message], user_message: str) -> ChatResult
    .stream_chat(history: Sequence[Message], user_message: str) -> Iterator[str] (+ a way to get the final ChatResult after)
    .build_context(history: Sequence[Message]) -> list[Message]   # the selection step alone, no provider call
```

**Concrete consumer:** `adapters.py::build_chat_context` plus the manual
orchestration inline in the Flask `/chat` and `/upload` routes — a real,
working implementation that exists today, hand-assembling exactly this
sequence (select context → prepend system prompt → call provider → wrap
reply) with no reuse across its two call sites. This is the same
"extract from ≥1 real implementation" pattern every other piece of this
framework was built from (`PinnedRecencyStrategy` from
`context_builder.py`, `GroqProvider` from `summarizer.py`, `Summarizer`
from `summarize_messages`). This is not a new kind of justification —
it's the same one, applied to the one piece of orchestration logic that
was never extracted because it lived in the application layer from the
start.

**Design decision: stateless, not stateful.** `ContextManager` does not
hold conversation history. `chat()` takes the current history as an
argument and returns the new messages to append — it does not remember
anything between calls. This mirrors every other piece of this
framework (`Message` is frozen and has no `id`; `ContextStrategy.build()`
takes the full list every time) and is deliberate, not an oversight:
see §7 for why a stateful "session" is explicitly rejected.

**Design decision: no auto-summarization, no persistence, no
telemetry system built in.** `ContextManager` composes exactly two
things — a strategy and a provider. It does not decide when to
summarize (today, summarization is 100% manually triggered — nothing
in the current system exercises "auto-summarize on overflow," so
building it would be a new behavior, not an extraction of an existing
one). It does not persist anything. It does not emit events. A caller
who wants auto-summarization calls `Summarizer.summarize()` themselves
and splices the result into the history before the next `.chat()` call
— composable without `ContextManager` needing to know summarization
exists.

**Design decision: the result must be transparent, not opaque.**
`ChatResult` should carry the response text *and* the underlying
`ContextResult` (what was kept, what was excluded) *and* the new
`Message` objects to append to history. A caller building telemetry,
logging, or a UI progress bar needs this data — if `ContextManager`
swallows it and returns only a string, every caller has to re-derive
what happened, exactly the problem `ContextResult.excluded` was built
to solve for `ContextStrategy` itself (ADR 0004).

**Self-challenge:** is a new class actually necessary, or is
`adapters.build_chat_context` — fifteen lines, a plain function — proof
that a *documented pattern* (a "cookbook" recipe) is enough, and a class
adds ceremony without adding capability? This is a fair challenge and
the reason `ContextManager` should stay deliberately thin rather than
growing into a god object. But the counter-holds: the user-facing API
this review was asked to design is explicitly `manager.chat(...)`, not
"copy this recipe into your own code" — and "copy this recipe" is
exactly the kind of duplication (once per consumer) that justified
extracting Strategy, Provider, and Summarizer in the first place. The
resolution is not "don't build it," it's "build it thin": the same
discipline that kept `Summarizer` from growing eligibility checks or
output labeling (ADR 0007) should keep `ContextManager` from growing
persistence or auto-summarization.

**Alternatives considered and rejected:**

- **`ChatSession`** — name implies stateful history tracking. Rejected
  for the same reason a stateful session is rejected in §7: no concrete
  consumer needs the framework to own persistence, and it reintroduces
  the identity questions `Message` deliberately avoided (ADR 0002's
  "no `id`" reasoning).
- **`ContextBuilder`** as a *separate* class from `ContextManager` —
  redundant. The "just select context, don't call a provider" need is
  real (inspecting what would be sent, without spending money on a real
  call) but doesn't need a second top-level class — it's the
  `.build_context()` method on `ContextManager` above.
- **`Pipeline`** (a generic, configurable N-step chain) — no concrete
  consumer assembles a dynamic pipeline today; the one real orchestration
  need has a fixed, simple shape (strategy → provider). A generic
  pipeline abstraction would be solving a more general problem than
  anything that currently exists to justify it — the same trap avoided
  for `CompositeStrategy` (§4) and `Registry` (§3).

**Should `Message`, `TokenBudget`, `ContextStrategy`, `LLMProvider`,
`Tokenizer`, `Summarizer` remain independently importable from their
owning subpackages, not just through `ContextManager`?** Yes — an eval
harness or a caller doing something `ContextManager` doesn't support
(e.g. calling a strategy with no provider at all) needs the low-level
pieces directly. `ContextManager` is a convenience layered on stable
primitives, not a replacement for them, the same relationship
`requests.Session` has to the lower-level pieces it's built from.

**One exception to "the top-level package re-exports nothing" (ADR
0002):** `ContextManager` is a strong, deliberate candidate for
`from contextshift import ContextManager` — if it becomes the framework's
primary entry point (which is the explicit goal), it is exactly the one
thing worth the top-level exception ADR 0002 didn't otherwise grant.
Everything else stays reachable only through its owning subpackage, as
today.

**Tradeoffs:** a thin orchestrator is an additional public class to
version and support; the alternative (recipe-only) has zero maintenance
surface but a worse first-five-minutes experience and no artifact to
extract eval-harness or CLI reuse from. **Risk:** scope creep — every
future feature request ("can `ContextManager` also retry on rate
limits," "can it log," "can it cache") will look like a natural
extension point. The mitigation is the same discipline already
established: reject each one until it has a concrete consumer, exactly
as `Summarizer` has for two review cycles now. **Migration impact:**
additive only — `adapters.py` keeps working unchanged until a
deliberate later phase (§10, Phase 2) migrates the Flask app onto it,
mirroring how Step 8 only cut over once every library piece was already
proven independently. **Confidence: high** that orchestration is the
real gap; **medium** on the exact method signatures above, which should
be treated as a first draft to be pressure-tested against the actual
Flask cutover (Phase 2), not frozen here.

## 3. Package structure

Recommend **zero new top-level packages right now.** Going through the
candidates named, each with its concrete-consumer test and its trigger
condition for reconsidering:

| Candidate | Verdict | Why | What would change the answer |
|---|---|---|---|
| `providers/` (rename of `llm/`) | Not yet | Only one capability protocol (`LLMProvider`) exists; renaming for a plural that doesn't exist yet is the same anticipatory move ADR 0002 rejected for `Message.timestamp` | A second capability protocol (most plausibly Vision, §5) actually getting built — bundle the rename into *that* unit of work, don't do it speculatively now |
| `memory/`, `sessions/` | No | No concrete consumer needs framework-owned persistence (§7). The fact the question lists both names for what might be the same concept is itself a sign this area isn't well-formed enough to build | A caller genuinely needing pluggable storage backends (Redis, Postgres, file) with a common interface — not the same thing as "the framework needs to remember things" |
| `pipeline/` | No | No concrete consumer assembles a dynamic multi-step chain; the one real orchestration need is fixed-shape (§2) | A second orchestration shape emerges that `ContextManager` genuinely can't express |
| `evaluation/` | No | Zero eval/scoring logic exists anywhere in this repo to extract an interface from — see §1 | An actual eval harness gets built (likely as a separate project) and a genuine common interface emerges from real use, not from guessing |
| `registry/` | No | Still one strategy, one provider — a registry with one entry is exactly the situation ADR 0004 and ADR 0007 already rejected, twice, for the same reason | A second concrete strategy *or* provider implementation actually lands |
| `plugins/` | No | Implies a discovery/loading mechanism (e.g. Python entry points) presupposing a third-party ecosystem that doesn't exist. Structural Protocols already deliver "plug in your own X without modifying ContextShift" (§4, §8) — a discovery mechanism is a different, bigger thing nothing needs yet | Real external contributors publishing their own strategies/providers as separate packages who want them auto-discovered, not just importable |
| `config/` | No | All configuration today is plain constructor kwargs, which are type-checked, IDE-discoverable, and already work | A consumer needs to instantiate a strategy/provider *from* a file or string (e.g. a CLI flag) — that's a concrete, narrow need, not a general config-object system (§6) |
| `events/` | No | No telemetry consumer exists; a plain-Python `ContextManager` is already wrappable/subclassable for logging with zero framework support, *provided* its results are transparent (§2, §8) | A consumer needs to observe *inside* a call, not just its result — not currently the case |
| `serialization/` | No | `dataclasses.asdict()` already covers "turn a Message into JSON" adequately; nothing needs schema versioning or cross-language contracts yet | A REST API or cross-process boundary wrapping ContextShift emerges with real serialization requirements |

**Where does `ContextManager` live?** A new top-level module,
`contextshift/manager.py` (or similar — naming is implementation detail,
not architecture), re-exported at the package root per the exception
noted in §2.

**Confidence: high** across this table — each rejection restates a
principle this project has already applied at least once, not a fresh
judgment call, with the partial exception of the `providers/` rename,
which is a genuine judgment call (noted as **medium** confidence) worth
your explicit input rather than a unilateral "no."

## 4. Strategy system

**Can third parties implement strategies without modifying ContextShift
today?** Yes — verified, not assumed. `ContextStrategy` is a structural
`Protocol`; `class MyStrategy: def build(self, messages, budget): ...`
satisfies it with zero import from `contextshift` beyond type hints,
which aren't even required at runtime for structural conformance. This
was the explicit design goal of ADR 0005 and it holds.

**What's actually missing is tooling *around* that already-working
extensibility, and all of it is correctly deferred:**

- **`StrategyRegistry`** — no, same reasoning as `registry/` in §3.
  Deferred (again) until a second strategy exists.
- **`CompositeStrategy` / `StrategyPipeline`** (combine or chain
  strategies) — no concrete consumer; with only one strategy in
  existence there is nothing to compose, and designing composition
  semantics against a single data point risks getting the shape wrong
  in exactly the way ADR 0002 warned about. Revisit once ≥2 strategies
  exist *and* someone has an actual reason to chain them — plenty of
  frameworks never need this because callers just pick one strategy per
  use case.
- **`StrategyConfig`** — no, see §6.
- **Metadata / capability advertisement** (e.g. "do I need a tokenizer,"
  "do I support pinning") — the most plausible near-future addition of
  this group, but still no concrete consumer today (no eval harness or
  registry exists to read such metadata) and no real data to know what
  fields it would need. Flagged as worth watching, not building.

**Confidence: high.** This section restates already-validated project
precedent rather than introducing new judgment calls.

## 5. Provider system

**Should one `LLMProvider` interface grow new methods, or should
capabilities become separate protocols?** Separate protocols — and this
isn't a fresh call, it's already-established precedent from ADR 0006 and
ADR 0010 being applied consistently: ADR 0006 scoped `LLMProvider` to
exactly two methods and explicitly excluded embeddings/tool
calling/vision. ADR 0010 then analyzed image understanding specifically
and concluded it's "a genuinely separate capability... different input
shape, no conversation history, different model" — not a
retrofit candidate for `LLMProvider`.

Growing one interface to cover unlike request/response shapes (a plain
`Message` sequence for text vs. multi-part content for vision vs. a
vector for embeddings) means either optional-parameter bloat most
implementations ignore, or type-signature contortions. Separate,
minimal protocols avoid both, and nothing stops one concrete class
(e.g. a hypothetical `GeminiProvider`) from implementing several
protocols at once — Python's structural typing makes that free.

**Which capability protocol, if any, is actually justified next?**
Vision, specifically — because it's the only one with a real, working
reference implementation to extract from
(`analyze_image_with_gemini`, currently outside the library entirely
per ADR 0008). Embeddings, tool calling, reranking, and structured
output have zero implementation anywhere in this repository — building
interfaces for those now would mean designing from nothing, which this
project has never done and shouldn't start now.

**Self-challenge:** is scheduling a vision protocol actually Framework
v2 scope, or a distraction from the orchestration gap that's the real
subject of this review? Vision answers a *capability breadth* question;
Framework v2's chartered problem is *usability/shape* (can someone build
on this without seeing the Flask app). These are different questions.
Recommendation: treat a vision protocol as available-to-schedule
whenever you want it, but not a required Framework v2 phase — §10 lists
it as optional, not sequenced.

**Confidence: high** on separate-protocols-over-growing-one-interface
(directly reaffirms two existing ADRs); **medium** on whether vision
specifically belongs in this roadmap at all, given the self-challenge
above.

## 6. Configuration

**No config objects** (`ContextShiftConfig`, `ProviderConfig`,
`TokenizerConfig`, `StrategyConfig`). Every constructor today
(`TokenBudget(max_tokens=..., safety_margin=...)`,
`PinnedRecencyStrategy(recent_buffer=...)`,
`GroqProvider(api_key=..., model=..., base_url=...)`,
`Summarizer(provider, max_tokens=...)`) already *is* the configuration
mechanism — type-checked at construction, IDE-discoverable, and
requires no extra indirection layer to learn.

**Concrete trigger that would change this:** a consumer needing to
instantiate a strategy or provider *from* an external representation —
a CLI flag (`--strategy=pinned_recency --recent-buffer=6`), a YAML file,
an environment variable. That's a narrow, real need for a small
`from_dict`/`from_env` convenience on specific classes, not a general
`*Config` object hierarchy across the whole framework. Build the narrow
thing when that consumer exists (most likely: a future CLI harness),
not a general system now.

**Confidence: high.** No new judgment call — this is ADR 0002's
"no premature API surface" principle applied to a new area.

## 7. Sessions

**No new stateful concepts** (`Session`, `Memory`) should be added.
Two of the five terms in the question already exist, just not under
those names:

- **"Context"** already exists — `ContextResult`, the output of a single
  `ContextStrategy.build()` call.
- **"Conversation" / "History"** already exists — `Sequence[Message]`,
  used consistently everywhere in this codebase as the representation
  of a conversation's messages. These two names are redundant with each
  other, not with something missing.
- **"Session"** and **"Memory"** both imply a stateful, persisted,
  addressable entity — and the fact the question offers two overlapping
  names for what might be the same thing is itself evidence this
  concept isn't concrete enough to design correctly yet. No consumer
  today needs the *framework* to own persistence: the Flask app's
  SQLAlchemy table is its session/memory implementation, entirely
  bespoke, and that's the correct shape — `contextshift` staying
  storage-agnostic is precisely what lets it serve a chatbot with SQL,
  a CLI with a JSON file, and an eval harness with nothing persisted at
  all, using the exact same `Sequence[Message]` representation.

This directly supports the stateless design of `ContextManager` in §2:
a stateful session object would mean the framework taking a position on
persistence it has no concrete need to take.

**Confidence: high.**

## 8. Extension points

Four of five named extension points are **already fully solved**,
verified against the actual Protocol mechanism, not asserted:

- **Custom tokenizer, strategy, provider** — all three are structural
  Protocols; a third party implements the matching method(s) with zero
  dependency on `contextshift` beyond type hints. Already true today.
- **Custom storage** — solved by the framework *not* owning storage at
  all (§7). There is nothing to plug into because there is no built-in
  storage to route around.
- **Custom telemetry** — no special mechanism needed, *conditional on*
  `ContextManager`'s results staying transparent (§2): if `.chat()`
  returns a `ChatResult` carrying the full `ContextResult` and the new
  messages, a caller can already wrap, subclass, or decorate any of
  `ContextManager`/`ContextStrategy`/`LLMProvider` for logging with
  ordinary Python, no event system required. This is a design
  *constraint* on `ContextManager`'s return type, not a new package.

**No new extension-point infrastructure is needed.** This is a stronger
conclusion than the question implies, and it's worth stating plainly:
the Protocol-based design already delivered on "plug in without
modifying ContextShift" as its core premise (ADR 0005) — Framework v2
doesn't need to add a plugin *system* on top of that, it needs to keep
not breaking it.

**Confidence: high** on tokenizer/strategy/provider/storage;
**medium** on telemetry, since it depends on `ContextManager`'s result
shape actually being designed transparently (§2), which hasn't been
tested against a real consumer yet.

## 9. Stability

Conservative, per your instruction. Recommend the stable-for-2.0 surface
be **close to what already exists**, largely unchanged by this review:

**Stable:**
- `core.Message`, `core.TokenBudget` — validated through two rounds of
  deliberate field-minimization (ADR 0002); additive-only changes from
  here (a new optional field is non-breaking).
- `strategies.ContextStrategy`, `strategies.ContextResult` — validated
  against one full real implementation plus exhaustive characterization
  tests.
- `llm.LLMProvider` — same basis.
- `tokenizers.Tokenizer` — same basis, trivial surface.
- `summarization.Summarizer` — the concrete class's public shape
  (constructor, `.summarize()`) is stable; whether summarization
  *becomes* a Protocol with multiple implementations is still open and
  unrelated to this class's current stability.
- `ingestion.extract_text_from_pdf`, `ingestion.prepare_image_for_vision`
  — narrow, characterization-tested pure functions.
- The one reference implementation of each protocol
  (`PinnedRecencyStrategy`, `GroqProvider`, `HeuristicTokenizer`) —
  stable at the public-constructor level; internals remain free to
  change.

**Explicitly *not* stable yet:**
- **`ContextManager`**, once built — should ship provisional/beta for at
  least one full cycle (build it, cut the Flask app over to it in Phase
  2, see if the shape survives contact with its real consumer) before
  being declared stable, exactly the same bar every other piece of this
  framework had to clear. Nothing here earns stability on day one.
- Everything rejected in §3–§8 (registry, composite strategy, config
  objects, sessions, plugins, events, evaluation, a second capability
  protocol) — not applicable; they don't exist.

**Confidence: high.** This section is nearly conclusion-free relative to
the rest — it mostly confirms what four ADRs and 271 tests already
established, with one deliberate exception (`ContextManager`'s
provisional status).

## 10. Roadmap

Small, independent, each compiling, testable, and releasable on its own
— the same discipline as the original migration's ten steps.

**Phase 1 — `ContextManager`, built in isolation.** Extract from
`adapters.py::build_chat_context` and the Flask routes' inline
orchestration, exactly as every prior extraction in this project worked:
port mechanically, characterization-test against what the Flask app
currently does by hand, do not wire it into `app.py` yet. Independently
reviewable; the Flask app is completely unaffected until Phase 2.

**Phase 2 — Cut `app.py`/`adapters.py` over to `ContextManager`.**
Mirrors Step 8's playbook precisely: only once Phase 1 is proven does
the one real consumer actually adopt it, which is what validates (or
invalidates) the design in §2 for real. This phase is where
`ContextManager` graduates from provisional toward stable (§9).

**Phase 3 — Promote a minimal public fake provider.** Small, low-risk,
concretely justified now that "external developers" and "eval harness"
are named target users rather than hypothetical ones (§1, §8). Needs an
explicit "where does this live" decision as part of the phase (it can't
stay in `tests/`, which isn't shipped in the installed package) — not
resolved here.

**Phase 4 (optional, not required for Framework v2) — Vision
capability protocol.** Already fully designed in ADR 0010 ("Step V"),
with a real reference implementation ready to extract from
(`analyze_image_with_gemini`). Per the §5 self-challenge, this answers a
capability-breadth question, not the usability/orchestration question
Framework v2 is chartered around — schedule it independently, on its
own timeline, not because it's convenient to bundle.

**Not scheduled, no phase number, pending future concrete need:**
strategy registry, composite/pipeline strategies, config objects,
session/memory persistence, a plugin discovery mechanism, an events
system, a second capability protocol beyond vision, an `evaluation/`
package. Each has its trigger condition named in §3–§8; none of them
are triggered today.

**Confidence:** **high** that Phase 1 → 2 is the correct, minimal,
justified sequence; **medium** on Phase 3's exact shape (needs a "where
does the public fake live" decision this review doesn't make);
**low-to-medium**, deliberately, on whether Phase 4 belongs in this
roadmap at all — flagged as optional precisely because that's a genuine
open question, not a settled one.

## Phase implementation status

Added as Phase 1, Phase 2, and Phase 3 landed, recording what the
Roadmap above left open rather than rewriting it.

**Phase 1 (`ContextManager`, built in isolation): complete.**
`contextshift/manager.py`, characterization-tested against the exact
duplication in `adapters.py::build_chat_context` and the Flask routes'
inline orchestration, as planned. Not wired into `app.py` yet, as
planned.

**Phase 2 (cut `app.py`/`adapters.py` over): complete.**
`adapters.py::build_chat_context` is deleted; `/chat` and `/upload`'s
PDF path now call `adapters.build_context_manager().stream_chat(...)` /
`.chat(...)`. Confirmed via characterization tests and real,
network-verified manual requests that application behavior is
unchanged. `ContextManager` has graduated from provisional toward
stable per §9.

One finding surfaced during Phase 2: `ChatResult.user_message` is not
consumed by either real call site — `/chat` uses `stream_chat()`,
which never returned it; `/upload`'s PDF path uses `chat()`, which
does, but the route must persist the user's message *before* calling
the provider (to preserve the app's existing behavior of keeping that
message even if the provider call then fails), which is *after*
`chat()` would return it. Kept provisionally rather than removed — see
the note on `ChatResult.user_message` in `contextshift/manager.py`.
Revisit once a second real consumer exists.

**Phase 3 (promote a minimal public fake provider): complete.** The
"where does this live" question this Roadmap left open is resolved as
`contextshift/testing.py`, a single module (mirroring
`contextshift/manager.py`'s shape) rather than a subpackage —
`FakeLLMProvider` is one class, and nothing today needs a second test
double in this module. `tests/fakes.py` is deleted; the test suite now
imports the same public `contextshift.testing.FakeLLMProvider` any
external consumer would. Not re-exported at the package root — `from
contextshift.testing import FakeLLMProvider`, per the target API in
§1, keeping the top-level re-export exception (§2) to exactly
`ContextManager`.

**Phase 4 (Vision capability): complete.** Implemented as a separate
design review and approval cycle, not bundled into this record's
original Phase 1–3 sequence — consistent with §10's own framing of
Phase 4 as independent, on its own timeline. `contextshift/vision/`
(`VisionProvider` protocol + `GeminiVisionProvider`) mirrors
`contextshift/llm/`'s shape exactly: one capability-oriented interface,
one concrete vendor implementation, image preprocessing left to
`contextshift.ingestion` rather than duplicated inside the provider
(ADR 0008, ADR 0010). `analyze_image_with_gemini` is deleted from
`utils/file_processor.py`; `/upload`'s image branch now calls
`adapters.build_vision_provider().describe(...)`. One deliberate API
adjustment from the original design review: `describe()`'s `prompt`
parameter is `str | None = None` rather than required — `None` is the
capability's own signal for general-description behavior, not
caller-owned framing text, which is a narrower reading of "prompt
ownership stays outside the framework" than every other prompt in this
project (`_CHAT_SYSTEM_PROMPT`) gets, made deliberately for this one
capability, not a precedent applied automatically elsewhere.

## Non-goals

Everything below is grounded in a decision already made somewhere in
this repository, not a fresh opinion. Two different kinds of "non-goal"
are mixed together in the prompt for this section, and it's worth
telling them apart rather than flattening them into one list:

**Permanent, structural non-goals** — things ContextShift will not own
regardless of how many future phases land, because owning them would
contradict the premise stated in `docs/architecture.md`: *"if the web
application disappeared tomorrow, would the `contextshift` library
still be useful to another developer or researcher?"* A library that
owned a database, an HTTP server, or a UI couldn't answer yes to that
question — it would only be useful to whichever one application it had
bound itself to.

- **Persistence and databases.** `core.Message` has no `id` field —
  ADR 0002 rejected it explicitly: *"identity is owned by whatever
  stores the message... not by the message itself."* `contextshift/`
  imports nothing from `models.py` or `config.py`'s
  `SQLALCHEMY_DATABASE_URI`; `adapters.py` exists specifically to
  translate ORM rows *out of* persistence and into `core.Message`
  before the library ever sees them (ADR 0001). This is not "not built
  yet" — the type shape already forecloses it.
- **Vector stores.** No embeddings capability exists (`LLMProvider` was
  explicitly scoped to `complete`/`stream` only, ADR 0006) and the one
  existing strategy doesn't do retrieval. If a future semantic-retrieval
  `ContextStrategy` is ever built, whatever vector store it uses
  internally is that strategy's own business, invisible behind the
  `ContextStrategy` Protocol — `contextshift` itself will never bundle
  or require a specific one.
- **HTTP servers.** The Flask app *is* the HTTP server; `contextshift/`
  has zero web-framework dependency (`docs/architecture.md` dependency
  rule #1–2) and stays that way by construction — a library that spoke
  HTTP itself couldn't be "equally usable from a web app, a CLI, a
  notebook, or an evaluation harness."
- **UI.** No UI code has existed in `contextshift/` at any point in this
  migration — `templates/` and `static/` have always been exclusively
  part of the example Flask application, never touched by any of the
  ten prior ADRs.
- **Prompt management.** The most consistently reinforced non-goal in
  this project's history: ADR 0004 excluded system-prompt construction
  from `ContextStrategy`, ADR 0006 excluded it from `LLMProvider`, ADR
  0007 excluded the `"[SUMMARY]"` label from `Summarizer`. The one place
  that owns actual prompt text today is `adapters.py`'s
  `_CHAT_SYSTEM_PROMPT` — application-side, on purpose, every time this
  question has come up.

**Deferred by design, not forever** — things ContextShift deliberately
doesn't need in order to work, because the problem they'd solve is
already solved a different way. These could exist someday without
contradicting anything above; they simply aren't required for the
library to be complete.

- **Agent runtimes and workflow engines.** `ContextManager` (this
  phase) orchestrates exactly one fixed shape — strategy then provider
  — not a general step-chain or an autonomous multi-step loop. §2 of
  this record rejected a generic `Pipeline` for the same reason: no
  concrete caller assembles a dynamic chain today.
- **Telemetry systems.** Solved by transparency instead of an event bus:
  if `ContextManager`'s results expose what a strategy kept and
  excluded (this phase's explicit transparency requirement), a caller
  can already log or trace by wrapping plain Python objects — no
  framework-provided mechanism is needed for that to work.
- **Plugin discovery.** Solved by structural Protocols instead of a
  loading mechanism: ADR 0005 already delivered "implement a matching
  method, no import from `contextshift` required." A discovery system
  (entry points, auto-registration) would solve a *different* problem —
  finding third-party implementations you didn't write — that has no
  consumer while this remains a single-repository project.
- **Configuration systems.** Solved by constructor parameters: every
  concrete class in this library takes its configuration as typed
  `__init__` arguments (`TokenBudget(max_tokens=...)`,
  `PinnedRecencyStrategy(recent_buffer=...)`), and nothing today
  instantiates one from an external file or string that would justify
  more than that.
- **Evaluation framework.** Nothing in this repository has ever scored a
  strategy or computed a metric — there is no implementation to extract
  a common interface from, the same bar every other abstraction in this
  project had to clear. `contextshift` is meant to make an eval harness
  *buildable as a separate project*, not to contain one.

## Consequences

**Easier:** a chatbot, CLI assistant, or eval harness builder gets one
orchestration call instead of having to read `adapters.py` and
reimplement its fifteen lines. The framework's public surface grows by
exactly one class, not by a config system, a plugin system, and a
session system built speculatively alongside it.

**Harder:** none identified beyond the ordinary cost of one more class
to maintain and eventually stabilize.

**Forecloses:** treating "we're building a framework now" as license to
add registries, config objects, or session management without a
concrete consumer for any of them. The rule that got this project to a
clean v1.0 — earn it, don't anticipate it — is the same rule that gets
it to a clean v2.0.
