# 0007 — The Summarizer domain service

## Status

Accepted.

## Context

Step 6 extracts the application's one summarization operation
(`utils/summarizer.py::summarize_messages`) into a service that depends
on `LLMProvider` (Step 5) rather than on Groq directly. Unlike Steps 4
and 5, this step wasn't framed as "design the smallest interface for
multiple X" -- there's one summarization approach in the application
today, and the instructions were about separating *what to ask a model*
from *how to talk to it*, not about designing for multiple summarization
strategies. Several scope questions still needed resolving.

### Class or bare function?

`Summarizer` is a class holding an injected `LLMProvider`, not a bare
`summarize(messages, provider)` function -- matching the shape of
`PinnedRecencyStrategy` and `GroqProvider`, even though (unlike those
two) there's no `Protocol` here yet for it to conform to. The reason is
dependency-holding, not interface conformance: a caller constructs one
`Summarizer(provider)` and reuses it, the same way a `GroqProvider` is
constructed once and reused across many `complete()`/`stream()` calls,
rather than threading a provider through every call site by hand.

### Why no `Summarizer` Protocol yet

Consistent with deferring a strategy registry in Step 4 until a second
strategy existed to make one meaningful: there is exactly one
summarization approach in this application. Introducing a `Protocol`
now would mean guessing at what a second approach's interface should
look like (single-shot vs. iterative/hierarchical summarization might
not even share a signature) with nothing concrete to validate the guess
against. If and when a second approach is built, that's the moment to
extract an interface from two real implementations, not before.

### What "deciding what should be summarized" means here

Read literally, this could mean either "which messages are eligible"
(filtering) or "how to represent each message in the prompt." It means
the latter. The eligibility question -- excluding archived/pinned
messages, requiring at least two messages before bothering -- lived in
the Flask route in the legacy implementation, not inside
`summarize_messages()` itself, and follows the same boundary already
established for `is_archived` in Step 2 (ADR notes on `core.Message`):
persistence-shaped filtering happens upstream, before messages reach the
library. `Summarizer.summarize()` unconditionally summarizes whatever
list it's given, exactly as `summarize_messages()` did -- including the
degenerate case of an empty list, which legacy never guarded against
either. Preserving that permissiveness is the mechanical-port
instruction working as intended, not an oversight.

"How to represent each message in the prompt" is real and was ported
exactly: legacy's `role = "user" if msg.role == "user" else "assistant"`
maps *any* non-"user" role -- including "system" -- to "assistant" in
the transcript. A hidden consequence worth naming: if a previous
`"[SUMMARY]"` message (`role="system"`) were ever included as input to a
later summarization pass, it would be transcribed as if the assistant
had said it. This is preserved as-is, not "fixed," per the
mechanical-port instruction.

### Why the output carries no `"[SUMMARY]"` prefix

`app.py`'s route builds `summary_content = f"[SUMMARY] {summary_text}"`
-- the prefix is added by the *caller*, not by `summarize_messages()`
itself. This is a display/storage convention specific to how the
original application tags summary messages in its chat history for the
UI, not part of what "summarization" means as an operation -- a CLI or
eval harness consuming `Summarizer.summarize()` wants the clean summary
text, not an artifact of one particular application's tagging scheme.
This directly extends the pattern already established twice: ADR 0004
excluded system-prompt construction from `ContextStrategy`, ADR 0006
left it unresolved for `LLMProvider`, and this step resolves it the same
way for summarization output: application-specific framing stays outside
the library.

### `max_tokens` vs. `temperature`, revisited

Applying the same test used in ADR 0006: does this value vary across
current, concrete usage? `max_tokens=512` is hardcoded at
`summarize_messages`'s one call site, never varied -- by that test alone
it looks like a `temperature`-style internal constant. It's exposed as a
constructor argument anyway, because the test isn't the only
consideration: `temperature` is a generic sampling parameter incidental
to Groq specifically, while "how long may a summary be" is a natural,
expected dial on summarization *as a concept*, not an implementation
detail of any one provider. `recent_buffer` (ADR 0004) was promoted to
configurable on the same reasoning -- it defines what kind of strategy
`PinnedRecencyStrategy` is, not an incidental setting.

## Decision

`Summarizer(provider: LLMProvider, max_tokens: int = 512)`, with one
method, `summarize(messages: Sequence[Message]) -> str`. Constructor
validates `max_tokens > 0` (new configurability earns invariant
validation, consistent with `TokenBudget`, `recent_buffer`, and
`GroqProvider.api_key` in earlier steps). No `Protocol`, no eligibility
checks, no output labeling -- all deliberately excluded per the
reasoning above.

## Consequences

**Easier:** `Summarizer` is testable with nothing but `FakeLLMProvider`
-- no network, no Groq, no Flask. A second summarization approach, if
one is ever built, has a real implementation to compare against when
designing an interface, rather than a speculative one.

**Harder:** none identified -- this is a narrower, more cleanly-scoped
service than the legacy function's surrounding route code suggested at
first glance.

**Forecloses:** treating "this is the only implementation so far" as
license to skip the same separation discipline applied to `Strategy` and
`Provider` -- `Summarizer` still depends only on the `LLMProvider`
interface, never `GroqProvider`, even with no second provider or second
summarization approach yet in existence to force the discipline.
