# 0010 — Multimodal architecture review

## Status

Accepted as analysis. Does not introduce any code. Per explicit
instruction, this review exists to reach a conclusion about whether a
dedicated vision capability is warranted and, if so, to describe its
shape at the level needed to sequence future work -- not to implement
`VisionProvider`.

## Context

Step 7 (ADR 0008) split `analyze_image_with_groq` and ported only its
pure-ingestion half. The AI-calling half remains in
`utils/file_processor.py`, unmigrated, because it didn't fit anywhere
that existed: not `contextshift.ingestion` (it's an AI concern), not
`LLMProvider` (text-only, ADR 0006), and building a new interface at
that point would have meant designing an abstraction from a single data
point. Step 8 left it there deliberately rather than forcing a fit.

This review asks the four questions needed to decide what comes next,
before `utils/file_processor.py` can be fully retired.

## 1. Is image understanding another form of `LLMProvider`, or a separate capability?

**Separate.** Three concrete, structural differences, not just
surface-level ones:

- **Input shape.** `LLMProvider.complete`/`stream` take
  `Sequence[Message]`, where `Message.content` is a plain `str`.
  Legacy's vision call sends a single message whose `content` is a
  multi-part array (`[{"type": "image_url", ...}, {"type": "text", ...}]`).
  `core.Message` cannot represent this without adding fields
  (`image_data`, `image_mime_type`, or similar) that every text-only
  strategy, `Summarizer`, and the pinned/recency algorithm would carry
  and never use -- exactly the speculative-field problem ADR 0002 named
  and rejected for `Message.timestamp`.
- **Conversational semantics.** `LLMProvider` calls replay a `Message`
  history -- that's the entire point of `ContextStrategy` feeding it.
  Legacy's `analyze_image_with_groq(file_bytes, mime_type, user_prompt)`
  takes no history at all; it's a single image plus a single prompt,
  structurally closer to a one-shot function call than a chat turn.
- **Model and request target.** A different model
  (`meta-llama/llama-4-scout-17b-16e-instruct` vs
  `llama-3.1-8b-instant`), different token/temperature defaults
  (`max_tokens=1024, temperature=0.5` vs the chat path's own defaults).

Only the *response* shape is shared (plain generated text back). That's
not enough to justify one interface -- unifying them would mean either
polluting `Message`/`complete()` with multimodal fields 95% of callers
never touch, or type-overloading `complete()` based on some vision-specific
argument, both of which contradict the minimal-interface discipline this
migration has held since Step 5.

## 2. If separate, what responsibilities belong to that interface?

Sketched for sequencing purposes only -- not implemented:

- **Input:** already-prepared image bytes, a MIME type, and a text
  prompt. Not a `Message` history -- legacy's vision call has none.
- **Output:** generated text, same shape as `LLMProvider.complete`'s
  return value.
- **Does NOT own image preprocessing.** That responsibility is already
  correctly placed in `contextshift.ingestion.prepare_image_for_vision`
  (Step 7). A vision interface should accept already-processed bytes,
  not redo resizing/conversion itself -- reusing Step 7's boundary, not
  reopening it.
- **Does NOT own base64/data-URL encoding, HTTP, retries, or auth** at
  the interface level -- those stay inside whatever concrete
  implementation talks to a specific vision backend, exactly as
  `GroqProvider` owns Groq's wire format while `LLMProvider` stays
  vendor-neutral.
- **Streaming:** no evidence it's needed. Legacy's vision call has no
  streaming variant, so per the "only expose capabilities with a
  concrete consumer" principle (ADR 0006), a first version would be
  non-streaming only -- unlike `LLMProvider`, which started with both
  `complete` and `stream` because both were genuinely used by different
  routes today.

A illustrative (not final, not implemented) shape:

```python
class VisionProvider(Protocol):
    def describe(self, image_bytes: bytes, mime_type: str, prompt: str) -> str: ...
```

## 3. Can document ingestion remain independent of image understanding?

**Yes, and Step 7 already proved it, not just assumed it.**
`contextshift.ingestion` has zero dependency on any AI/vision code today
-- `test_ingestion_characterization.py` verified `prepare_image_for_vision`'s
output is byte-identical to what legacy embeds in its Groq payload, with
`contextshift.ingestion` never importing `requests` or knowing Groq
exists. A future vision capability would depend on `ingestion`'s output
(processed bytes as input to a `describe()` call) -- never the reverse.
One-directional, consistent with every other dependency rule in this
migration.

## 4. Would a future local vision model fit naturally into the proposed abstraction?

**Yes.** A local model (e.g., a self-hosted vision-language model) needs
the same three inputs (image bytes, MIME type, prompt) and returns the
same output (text) -- nothing in the sketched interface assumes a
network call, Groq's data-URL format, or any vendor-specific
representation. A `LocalVisionProvider` implementing `describe()` by
running in-process or local-server inference instead of an HTTP request
fits the same interface a `GroqVisionProvider` would. This is the same
test already validated for `LLMProvider`/`GroqProvider` in ADR 0006,
applied here and holding up -- which is itself evidence the sketched
interface draws its boundary in the right place, not vendor-specific
convenience.

## Conclusion

A dedicated vision capability is warranted. It should be introduced as
its own migration step -- not retrofitted into `LLMProvider`, and not
implemented as a byproduct of this review. Proposed (not scheduled,
not implemented) as a future roadmap entry:

**"Step V — Vision capability."** Extract
`analyze_image_with_groq`'s AI-calling half into a new `VisionProvider`
interface (naming, exact signature, and module location to be decided
*when that step actually begins*, informed by whatever's learned
building it -- not pre-committed here), implemented first by a
`GroqVisionProvider`, consuming `contextshift.ingestion.prepare_image_for_vision`'s
output as input. Only at that point does `/upload`'s image branch cut
over, and only then does `utils/file_processor.py` become fully
retireable.

This step is **not scheduled** by this record. Whether it happens before
or after Step 9/10, or at all, is a separate decision for whenever it's
prioritized.

## Consequences

**Easier:** the next time vision work happens, it starts from a
reasoned interface sketch instead of an unexamined "just add a method to
`LLMProvider`" impulse -- the four questions above are already answered.

**Harder:** none introduced -- this record adds no code and changes
nothing about the current system.

**Forecloses:** implementing vision support by extending `LLMProvider`
or `Message` with multimodal fields. If a future implementer wants to
do that instead, it should supersede this record with its own
reasoning, not silently diverge from it.
