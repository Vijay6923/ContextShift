# 0009 — Application cutover scope and the adapter's design (Step 8)

## Status

Accepted.

## Context

Step 8 wires `app.py` to `contextshift/` for the first time. Per your
explicit redirect, scope was revised from the original migration plan:
only capabilities with a *complete* library implementation get cut over
-- context building, tokenization, summarization, text LLM interactions,
PDF text extraction. Image analysis stays on
`utils/file_processor.py::analyze_image_with_groq` until a dedicated
vision capability is designed (see ADR 0008). Several implementation
decisions came up while wiring the rest.

## Decision

### `adapters.py` lives at the repo root, not inside `contextshift/`

Per ADR 0001. It has two jobs: translate `models.Message` (ORM) into
`contextshift.core.Message`, and construct correctly-configured library
objects (`TokenBudget`, `PinnedRecencyStrategy`, `GroqProvider`,
`Summarizer`) from `config.Config`. Both require knowing about both
sides of the boundary, which is precisely why this code cannot live in
the library.

### `app.py` imports `adapters` as a module, never individual names from it

`import adapters` + `adapters.build_provider()`, not
`from adapters import build_provider`. This is not a style preference --
it's what makes the existing test suite's monkeypatching keep working.
Flask's test client drives calls through `app.py`'s route functions,
which look up `adapters.build_provider` fresh at call time when it's
accessed as a module attribute; `from adapters import build_provider`
would bind a local name at import time that a later
`monkeypatch.setattr("adapters.build_provider", ...)` wouldn't reach.
This is the exact pattern the pre-migration test suite already relied on
for `utils.summarizer` (`from utils import summarizer` +
`summarizer.call_groq(...)`), carried forward deliberately rather than
rediscovered by trial and error.

### `build_provider()` is a factory function, called fresh per request, never cached

`GroqProvider` validates `api_key` at construction (Step 5 / ADR 0006).
Legacy's equivalent check ran *inside* `call_groq`/`call_groq_stream`,
at call time -- meaning a missing `GROQ_API_KEY` let the app boot fine
and only failed the specific request that needed Groq. Constructing a
`GroqProvider` once at module import time in `app.py` would change that:
the app would refuse to boot at all with a missing key. `build_provider()`
stays a function, called inside each route, preserving legacy's exact
failure timing. `build_budget()`, `build_strategy()`, and
`build_tokenizer()` have no equivalent risk (their inputs are hardcoded
`Config` constants that always satisfy validation) but are functions too,
for API consistency within `adapters.py` rather than a mix of functions
and module-level constants that would raise the question of why some are
cached and others aren't.

### `build_chat_context()` resolves what ADR 0004 and ADR 0006 deliberately left open

Both records excluded system-prompt construction and OpenAI-dict
formatting from `contextshift/`, naming "whatever orchestrates a
strategy result into a provider call" as the eventual owner without
saying what that would be. It's this function: convert ORM messages to
`core.Message`, run `PinnedRecencyStrategy.build()`, prepend a
`core.Message(role="system", content=...)` carrying the application's
exact system prompt text, and hand the result straight to
`GroqProvider.complete()`/`.stream()` (which accept `Sequence[Message]`
directly -- no dict conversion needed at this layer at all, since
`GroqProvider` does that internally). The system prompt's exact wording
now lives in exactly one place: `adapters.py`.

### `compute_token_stats()` stays application-side, per ADR 0003

Reproduces legacy's `{current_tokens, max_tokens, percentage}` JSON
shape for the frontend's progress bar, built from
`contextshift.strategies.total_tokens()` and `TokenBudget.max_tokens`.
ADR 0003 flagged this as a strong candidate for staying outside the
library's public surface; this is that call made concrete.

### The `/chat` route's `with app.app_context()` nesting is preserved as-is, not fixed

Step 0 found and worked around a real bug: nesting a manual
`app.app_context()` inside a `stream_with_context`-wrapped generator
doesn't compose safely with Flask 3.x's per-iteration context handling,
under Flask's test-client context-preservation mode specifically. I
considered fixing it during this cutover, since `/chat` was being
rewired anyway and the fix would plausibly simplify the code (the
manual context push may be redundant with what `stream_with_context`
already provides). I did not, for the same reason nothing in this
migration touches behavior beyond what's explicitly asked: this step's
mandate was revised scope for *which capabilities* get cut over, not a
mandate to fix unrelated pre-existing bugs discovered along the way.
The exact same structure, bug included, is preserved. Flagging this
explicitly rather than silently deciding either way -- fixing it is a
five-minute change whenever you want it done.

### One pre-approved, cosmetic behavior difference now surfaces in practice

If `GROQ_API_KEY` is unset, legacy's error text is "GROQ_API_KEY is not
set in environment."; the new path's is "api_key is required" (from
`GroqProvider.__init__`, ADR 0006). Both are caught by the same
surrounding `except Exception` handlers and produce an equivalent JSON/SSE
error response -- this was already identified and accepted in ADR 0006's
review, not a new finding, but worth naming here since Step 8 is where
it actually becomes reachable through the running app for the first
time.

### `utils/` is no longer a single unit for Step 9's eventual deletion

After this step, `utils/token_manager.py`, `utils/context_builder.py`,
and `utils/summarizer.py` are fully dead code -- nothing in `app.py`
imports them. `utils/file_processor.py` is not: `analyze_image_with_groq`
is still load-bearing for the image-upload path, even though
`extract_text_from_pdf` inside the same file is now dead. Step 9's scope
is revised accordingly: delete the three fully-dead modules; leave
`file_processor.py` in place (or split it) until vision capability has a
home in `contextshift/`.

## Consequences

**Easier:** the running application now exercises
`contextshift.strategies`, `contextshift.tokenizers`,
`contextshift.summarization`, `contextshift.llm`, and
`contextshift.ingestion` (PDF) for real, on every chat, summarize, and
PDF-upload request -- this is no longer a library that merely has tests
passing in isolation.

**Harder:** the image-upload path is now visibly inconsistent internally
-- preprocessing *could* use `contextshift.ingestion.prepare_image_for_vision`
but the route doesn't call it, since doing so with no corresponding
vision-calling capability in the library would mean preprocessing
correctly and then handing the result to legacy code anyway, adding a
dependency for no behavioral benefit. The route's image branch is
untouched, calling legacy end to end, exactly as decided.

**Forecloses:** treating this cutover as proof the migration is
"basically done." Vision is a known, named gap, and the post-Step-8
architecture review below addresses it directly, on its own terms, before
any further deletion happens.
