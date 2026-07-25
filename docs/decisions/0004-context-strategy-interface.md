# 0004 — The ContextStrategy interface

## Status

Accepted.

## Context

Step 4 extracts the application's one and only context-selection
algorithm (`utils/context_builder.py::build_context`) into a reusable
abstraction that a second, third, and eventually many more strategies can
implement without touching each other or the application that consumes
them. The starting question, posed deliberately before any code was
written: what is the smallest interface that still allows multiple
strategies?

### What varies across strategies, and what doesn't

The legacy algorithm has three configuration inputs: `MAX_TOKENS`,
`TOKEN_SAFETY_MARGIN` (both already unified into `TokenBudget`, Step 2),
and `RECENT_BUFFER` (how many trailing messages count as "recent"). The
first two are budget-shaped and universal -- every strategy needs to know
how much room it has, regardless of its internal policy. `RECENT_BUFFER`
is not universal: it's specific to *this* strategy's definition of
recency. A semantic-retrieval strategy has no recency window at all. The
test applied throughout: a parameter belongs in the shared `build()`
signature only if every strategy, regardless of approach, needs it to do
its job. Only the candidate messages and the budget clear that bar.
Everything else is the strategy instance's own constructor configuration.

### What a strategy's output needs to express

The legacy function returns a bare `list[dict]`: a hardcoded system
message followed by OpenAI-formatted `{"role", "content"}` entries. Two
concerns are fused into that one return value: (1) *which messages were
selected*, and (2) *how to present them to a specific LLM provider's
chat-completions API, including what system prompt to use*. These are
different kinds of decisions made by different parts of the system --
selecting messages is what a strategy does; deciding on a system prompt
and a provider's wire format is a prompt-engineering / LLM-integration
concern that has nothing to do with which strategy chose the messages.
Fusing them would mean every future strategy (including ones with no
opinion on prompt engineering at all) has to know about OpenAI-shaped
dicts.

A separate, standing principle from earlier in this migration matters
here too: "every decision made by a strategy should be inspectable and
explainable." The legacy return value makes this impossible after the
fact -- once you have the final list, there's no way to know what was
excluded, or that anything was excluded at all, without re-deriving it
independently. This is a real, current requirement (stated as a goal for
the project as a whole), not a hypothetical one, so it's addressed now
rather than deferred the way `Message.timestamp` was in ADR 0002.

## Decision

**Interface:**

```python
class ContextStrategy(Protocol):
    def build(self, messages: Sequence[Message], budget: TokenBudget) -> ContextResult: ...
```

A structural `Protocol`, not an ABC, matching the precedent set for
`Tokenizer` in Step 3: a strategy is defined entirely by having a
matching `build` method, not by an inheritance relationship. A
third-party strategy implementation needs no dependency on this package
beyond the type it's structurally satisfying.

**Result type:**

```python
@dataclass(frozen=True, slots=True)
class ContextResult:
    messages: list[Message]   # kept, in order
    excluded: list[Message]   # dropped, in original relative order
```

Two fields, deliberately. `messages` is plain `Message` objects, not
OpenAI-format dicts, and carries no system prompt -- formatting a prompt
for a specific provider is scoped out of this step entirely (see
Consequences). `excluded` is the direct, current answer to "what did
this strategy exclude" -- the minimal amount of explainability that has
an actual consumer today (a caller, a test, or eventually an eval
harness, can now see what was dropped without re-deriving it). A richer
structured trace -- *why* each message was excluded (pruned as a
candidate vs. pruned as a recent message vs. never considered) -- was
considered and deliberately not built: nothing today consumes that
distinction, and per the same reasoning as ADR 0002, a field earns its
place by having a concrete consumer, not by being plausible for a future
one. Adding a richer trace later is additive, not breaking.

**Strategy-specific configuration lives on the constructor:**
`PinnedRecencyStrategy(recent_buffer: int = 6)`. `recent_buffer` is
validated to be at least 1 -- not preserving legacy behavior (legacy's
`RECENT_BUFFER` was always the hardcoded constant 6; a value of 0 was
never reachable), but a deliberate new invariant, because Python's slice
semantics make `non_pinned[-0:]` equivalent to `non_pinned[0:]` -- the
*entire* list, not zero elements. Since `recent_buffer` is now a
caller-supplied value for the first time, 0 needed an explicit decision
rather than inheriting an untested assumption from legacy code that
never had to consider it.

**Excluded messages are tracked by object identity, not recomputed by
value.** `Message` has value-based equality (Step 2), so two distinct
turns with identical role/content/token_count/is_pinned would collide
under a naive "excluded = original list minus final list" computation.
The implementation instead appends each message to `excluded` at the
exact moment it's popped from `candidates` or `recent`, preserving
identity and, as a consequence of candidates always being chronologically
older than recent messages, preserving overall chronological order too.

## Consequences

**Easier:** `contextshift.strategies` has no knowledge of OpenAI's API
shape, HTTP, or any specific LLM provider, and no strategy implementation
ever needs to. Adding a second strategy requires implementing one method
against plain `Message`/`TokenBudget` types, with no dependency on
`contextshift.llm` at all unless the strategy specifically needs to call
an LLM (e.g. a future summarization-based strategy).

**Harder / genuinely deferred, not resolved:** something downstream now
needs to own system-prompt construction and OpenAI-dict formatting --
almost certainly `contextshift.llm` (since it's about talking to a
provider) or the application-side adapter introduced at the Step 8
cutover. This step does not decide which; that's an open question for
whichever step actually needs the answer, consistent with this
migration's pattern of not resolving a design question before a concrete
consumer forces it.

**Forecloses, for now:** a strategy needing to call an LLM or another I/O
source as part of `build()` (e.g. computing embeddings on the fly) isn't
supported by this synchronous interface. Nothing in the current design
needs this yet -- the legacy algorithm is 100% synchronous and
deterministic, and this step's mandate was to preserve that exactly, not
anticipate it. If a future strategy genuinely needs it, that's a new
decision point, not something this ADR pre-commits to solving.
