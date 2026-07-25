# 0008 — The ingestion/AI boundary, and what Step 7 deliberately leaves unported

## Status

Accepted.

## Context

`utils/file_processor.py` has two functions. `extract_text_from_pdf` is
unambiguous: PyPDF2 parsing, no network, no AI -- pure ingestion.
`analyze_image_with_groq` is not: it does real image preprocessing
(Pillow resize/convert/re-encode) and then, in the same function,
base64-encodes the result, builds a Groq-specific multimodal payload,
and makes a retried HTTP call to a vision model. The instructions for
this step were explicit that these are different concerns and the
boundary between them should stay visible, even where legacy code
merged them.

### Why the function gets split, not just relabeled

"Preserve the existing implementation" (this step's instruction) could
be read two ways: preserve the *physical shape* of the function
(port it as one combined unit), or preserve the *behavior* of each of
its two halves independently while giving them separate homes. The
second reading is the one applied here, and it's the same reading
applied consistently since ADR 0004: system-prompt construction was
physically inline with context-selection in legacy's `build_context`,
but ADR 0004 didn't port them together just because they happened to be
adjacent -- it extracted the selection logic and named the prompt
construction as a different concern with a different home. ADR 0006 did
the same for the Groq-specific request payload versus the
provider-agnostic interface, and ADR 0007 did it again for the
`"[SUMMARY]"` label versus the summarization operation itself. Keeping
`analyze_image_with_groq` as one function inside `contextshift/ingestion/`
would mean the one subpackage whose entire premise is "no AI, no
network" contains a function that does both -- undermining the
boundary this step exists to make visible, not just to describe it in a
comment.

### What actually moved, and what didn't

**Moved, as pure ingestion** (`contextshift/ingestion/image.py`,
`prepare_image_for_vision`): the Pillow preprocessing -- RGBA/P/LA to
RGB conversion, thumbnailing above `MAX_DIMENSION_PX` (1568px, unchanged
from legacy), re-encoding as JPEG at `JPEG_QUALITY` (85, unchanged).
Same fallback behavior on any failure: original bytes and mime type
returned unchanged, a warning printed, no exception raised.

**Did not move, and remains in `utils/file_processor.py`,
untouched:** the base64 encoding, Groq multimodal payload construction,
the vision-specific model name
(`meta-llama/llama-4-scout-17b-16e-instruct`), and the HTTP
call-with-retry logic. This is a **deliberate, named gap**, not an
oversight:

- It isn't ingestion (Principle 1 rules this out directly: "LLM-based
  understanding is a different concern").
- It isn't `LLMProvider` either -- ADR 0006 already scoped vision out of
  that interface explicitly, since `complete`/`stream` are text-only
  capabilities and a vision call is a structurally different request
  (multimodal content, a different model, a different response shape
  isn't different, but the *request* shape is).
- Building a new `VisionProvider`-style interface now would repeat the
  mistake Step 1's original architecture.md made: designing an
  abstraction from a single data point before a second real
  implementation exists to validate the guess against (the same
  reasoning behind deferring a strategy registry in ADR 0004 and a
  `Summarizer` protocol in ADR 0007).

So the vision-calling code has nowhere principled to go yet. Rather than
force it into the nearest available box, it stays where it is. This is
Step 7's honest answer to review deliverable 3: yes, image analysis
should become its own capability, separate from ingestion -- and this
step already acts on that by refusing to co-locate the two, even though
it does not yet build image analysis's destination.

### A hidden assumption worth naming

Legacy's `except Exception` around the whole preprocessing block is
broader than a first read suggests -- it's not just "handle a corrupt
image," it also silently tolerates Pillow being unavailable at all
(an `ImportError` on `from PIL import Image` is caught by the same
`except Exception`, falling back to the original bytes exactly as a
decode failure would). This is why `prepare_image_for_vision` keeps the
`PIL` import local to the function rather than promoting it to module
level, even though Pillow is a hard requirement of this project
(`requirements.txt`) and that particular failure mode isn't reachable in
practice -- promoting the import would be a real behavioral change
(a missing Pillow would crash at module import time instead of
degrading gracefully at call time), not just a style cleanup.

## Decision

`contextshift/ingestion/` contains exactly two functions, both pure:
`extract_text_from_pdf(bytes) -> str` and
`prepare_image_for_vision(bytes, mime_type) -> tuple[bytes, str]`.
Neither makes a network call, imports `requests`, or references any
application/Flask type. The AI-vision-calling code remains, unmodified,
in `utils/file_processor.py`, explicitly out of scope for this step and
for the eventual Step 9 deletion of `utils/` -- that deletion cannot
happen until vision capability has a real home in `contextshift/`,
which is not decided by this record.

## Consequences

**Easier:** `contextshift/ingestion/` is testable with zero network
access and, for the PDF case, without even a real PDF file -- PyPDF2's
`PdfReader` is mocked at the boundary the same way `requests.post` was
mocked in Steps 5-6, since verifying this function's own logic (page
iteration, labeling, the no-text error path) doesn't require verifying
PyPDF2's own parsing correctness. For images, real Pillow-generated
test images are used directly (cheap and dependency-free, unlike
constructing a valid PDF by hand), plus a characterization test that
captures what legacy's `analyze_image_with_groq` actually embeds in its
base64 payload and asserts it's byte-identical to
`prepare_image_for_vision`'s output for the same input -- proving the
split introduced no drift, not just asserting it didn't.

**Harder:** the application's image-upload feature cannot be fully
cut over to `contextshift/` at Step 8 the way `/chat` and `/summarize`
can -- it will need to keep calling legacy's `analyze_image_with_groq`
(or an equivalent still living outside the library) for the AI half,
while the preprocessing half could use the new
`prepare_image_for_vision`. That's an accurate reflection of where the
architecture actually stands, not a problem to paper over now.

**Forecloses:** treating "the legacy function already worked, so leave
it alone" as sufficient reason to compromise the ingestion/AI boundary
this step's principles establish. A future vision-capability decision
(extend `LLMProvider`, a new `VisionProvider` protocol, something else)
gets to be made deliberately, from this clean starting point, rather
than inherited as a fait accompli from wherever the code happened to
land during extraction.
