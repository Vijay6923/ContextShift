# 0006 — The LLMProvider interface

## Status

Accepted.

## Context

Step 5 extracts the application's only LLM integration
(`utils/summarizer.py`'s `call_groq`/`call_groq_stream`) into the
library's first infrastructure abstraction -- the first subpackage that
does real I/O rather than pure computation. The explicit goal, stated
going in: this step is not about Groq, it's about defining an interface
any provider could satisfy, with Groq as its first consumer.

Two questions needed resolving that the earlier `ContextStrategy` work
(ADR 0004) had explicitly left open: what shape do messages take when
handed to a provider, and does anything decide on a system prompt.

## Decision

**Interface:**

```python
class LLMProvider(Protocol):
    def complete(self, messages: Sequence[Message], max_tokens: int = 1024) -> str: ...
    def stream(self, messages: Sequence[Message], max_tokens: int = 1024) -> Iterator[str]: ...
```

A structural `Protocol`, per ADR 0005 -- not re-justified here.

**`messages` is `Sequence[Message]`, not a list of OpenAI-shaped dicts.**
This resolves half of what ADR 0004 deferred: every other part of the
library already speaks `Message`; a provider that instead required
callers to pre-format a vendor-shaped payload would leak a transport
detail into every caller (strategies, summarization, the eventual
adapter). `GroqProvider` owns the `Message` → wire-format conversion
internally, as a transport concern -- exactly what Design Principle 3
("the rest of ContextShift should not know or care how Groq
communicates") asks for. **What ADR 0004 left open about *system prompt*
construction is still open** -- this interface has no opinion on
whether a caller includes a system message in `messages` or not; that
decision belongs to whatever orchestrates a strategy result into a
provider call, which doesn't exist yet (Step 8).

**`max_tokens` is a shared parameter; `temperature` is not.** The same
test applied in ADR 0004 to `recent_buffer`: does this value vary across
current, concrete call sites? `max_tokens` does -- the legacy
`/chat` route calls with the default 1024, `summarize_messages` calls
with 512. `temperature` does not; it is hardcoded to `0.7` in both
legacy functions, never varied anywhere in the application. `temperature`
stays an internal `GroqProvider` constant, not an interface parameter or
even a constructor argument -- adding configurability nothing currently
uses would be exactly the speculative addition Design Principle 4 rules
out.

**Only two capabilities: `complete` and `stream`.** No embeddings, no
tool calling, no structured outputs, no multimodal input, per Design
Principle 4. The application's image-analysis capability
(`analyze_image_with_groq`, in `utils/file_processor.py`) is a distinct,
already-separate code path calling a different Groq model with
multimodal payloads -- out of scope for this step, expected to be
addressed in Step 7 (`contextshift/ingestion/`), and not necessarily
through this same interface even then.

**`GroqProvider` takes `api_key`, `model`, and `base_url` as constructor
arguments, validated at construction (`api_key` required, checked
immediately) rather than read from a global `Config` at call time.** This
is the first subpackage that would have been tempted to import
`config.Config` for real, load-bearing reasons (it needs a real secret to
function) -- making it the first concrete test of ADR 0001's rule that
`contextshift/` never imports application configuration. It holds:
`GroqProvider` has zero knowledge that a Flask app, or any particular
config-loading mechanism, exists. Whatever constructs it (the Step 8
adapter, a CLI, a notebook) is responsible for supplying real values.

**No unified payload builder across `complete` and `stream`.** The
legacy `call_groq` payload has no `"stream"` key at all; only
`call_groq_stream`'s does. A shared builder taking a `stream: bool` and
always including the key (`False` for the non-streaming case) would very
likely behave identically against Groq's actual API -- but "very likely
identical" is not the same guarantee as "verified identical," and Design
Principle 2 explicitly names "request payloads" as something not to
touch this step. The two payloads remain separately constructed, exactly
mirroring legacy's structure. Only the `Message` → wire-format conversion
(`_to_wire_messages`), which has no legacy equivalent to diverge from
since legacy never had `Message` objects to convert, is shared between
them.

**No typed exception hierarchy.** Legacy raises bare `Exception(...)`
and `ValueError(...)`, with hardcoded human-readable messages, no
`LLMProviderError` or `RateLimitError` types. Ported as-is, per Design
Principle 2 ("do not improve... error handling... unless required for
correctness"). A typed hierarchy is a reasonable future improvement, but
it's a deliberate, separate decision to make later, not a side effect of
this port.

**No `logging` module.** Legacy uses bare `print()` for its
rate-limit/error diagnostics. Ported as-is, for the same reason.

**A `FakeLLMProvider` exists, but in `tests/`, not in `contextshift/`.**
Per your suggestion: a trivial in-memory implementation validates that
the interface is genuinely satisfiable without any of GroqProvider's
transport complexity, and lets strategy/summarization tests inject a
provider with no network calls. It is deliberately not part of the
production package (no `contextshift.testing` subpackage) -- nothing
today needs it to be importable outside this repository's own test
suite, and adding one would be exactly the kind of speculative addition
this step is otherwise avoiding.

## Consequences

**Easier:** a second provider (OpenAI directly, a local vLLM server, a
different vendor entirely) is a new class implementing two methods
against plain `Message` objects, with zero changes to any strategy or to
`contextshift.summarization` once it exists (see review deliverable 3 for
the concrete argument). Tests exercising anything that needs an
`LLMProvider` can use `FakeLLMProvider` and make zero network calls.

**Harder:** callers now need to construct `Message` objects (or use
whatever a strategy already returned) rather than handing a provider raw
dicts -- a non-issue for anything already using the rest of this library,
but it does mean `GroqProvider` cannot be used as a drop-in replacement
for the legacy free functions without a small adaptation shim, which is
exactly what the Step 8 adapter is for.

**Forecloses, for now:** any capability beyond text completion
(embeddings, tool calls, structured outputs, multimodal input) until a
concrete consumer needs it and a deliberate decision extends the
interface -- consistent with how every other interface in this migration
has been scoped.
