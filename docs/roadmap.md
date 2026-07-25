# Roadmap

This is a living document. See [`architecture.md`](architecture.md) for the
design this roadmap is executing toward, and [`decisions/`](decisions/) for
the reasoning behind specific choices made along the way.

## Migration in progress: extracting `contextshift/`

Goal: preserve the existing Flask app's behavior exactly while extracting
its context-management logic into an independent, zero-Flask-dependency
library, so the app becomes one consumer of that library rather than the
place the logic lives.

- [x] **Step 0** — Baseline test suite covering every route, plus direct
      characterization tests of `context_builder`/`token_manager` (the
      algorithm later steps will port). No production code changed.
- [x] **Step 1** — Scaffold the empty `contextshift/` package (six
      subpackages, docstrings only, no logic, nothing wired in yet).
- [x] **Step 2** — `contextshift/core/message.py` and `core/budget.py`:
      the plain, framework-independent domain types.
- [x] **Step 3** — Port `token_manager.py` → `tokenizers/heuristic.py`.
      Scoped down to per-text estimation only (ADR 0003); budget
      aggregation deferred to Step 4.
- [x] **Step 4** — Port `context_builder.py` → `strategies/pinned_recency.py`
      + `ContextStrategy` interface (ADR 0004). Highest-risk port in the
      migration; verified with a direct legacy-vs-new equivalence test
      over 13 scenarios, not just independent test coverage of each side.
- [x] **Step 5** — Port the Groq REST client → `llm/groq.py` behind an
      `LLMProvider` interface (ADR 0006). Verified with a direct
      legacy-vs-new comparison over mocked HTTP (happy path, 429 retry,
      exhausted retries, streaming, malformed SSE lines). A FakeLLMProvider
      in `tests/` validates the interface needs no transport complexity
      to satisfy.
- [x] **Step 6** — Port `summarize_messages` → `summarization/`, built on
      `llm/` (ADR 0007). Depends only on `LLMProvider`, never
      `GroqProvider`; verified with a direct legacy-vs-new prompt
      comparison across 4 scenarios.
- [x] **Step 7** — Port PDF extraction and image *preprocessing* →
      `ingestion/` (ADR 0008). AI-based image understanding
      (`analyze_image_with_groq`'s vision call) deliberately NOT
      ported -- it's an AI concern, not ingestion, and has no home yet
      (`LLMProvider` is text-only, ADR 0006; no `VisionProvider` exists).
      Remains in `utils/file_processor.py`, a named gap blocking Step 9's
      `utils/` deletion until vision capability is deliberately designed.
- [x] **Step 8** — Cutover, scope revised (ADR 0009): `app.py` now runs on
      `contextshift/` for context building, tokenization, summarization,
      text LLM calls, and PDF extraction. Image analysis deliberately
      **not** cut over -- `/upload`'s image branch still calls
      `utils/file_processor.py::analyze_image_with_groq` directly,
      unchanged, per your explicit redirect not to force it into
      `LLMProvider` just to complete the original plan. New
      `adapters.py` (repo root, not in `contextshift/`) does ORM↔`core.Message`
      translation and constructs configured library objects from
      `Config`.
- [x] **Post-Step-8 architecture review** — multimodal support, analysis
      only (ADR 0010). Conclusion: image understanding is a genuinely
      separate capability from `LLMProvider` (different input shape, no
      conversation history, different model) but cleanly separable from
      `contextshift.ingestion`, which Step 7 already proved independent.
      A dedicated vision capability is warranted, sketched but **not
      implemented or scheduled** -- see "Step V" below.
- [ ] **Step V — Vision capability** *(proposed, not scheduled)*. Extract
      `analyze_image_with_groq`'s AI-calling half into a new
      `VisionProvider`-shaped interface, consuming
      `contextshift.ingestion.prepare_image_for_vision`'s output.
      Naming/signature/module location deliberately left open until this
      step actually begins (ADR 0010). Only then does `/upload`'s image
      branch cut over and `utils/file_processor.py` become fully
      retireable.
- [ ] **Step 9** — Delete `utils/token_manager.py`, `utils/context_builder.py`,
      `utils/summarizer.py` (fully dead after Step 8). `utils/file_processor.py`
      stays, in whole or in part, until the multimodal review lands and
      vision capability (if warranted) has a home in `contextshift/`.
- [ ] **Step 10** (optional) — Package `contextshift/` as installable
      (`pyproject.toml`, `pip install -e .`).

## Beyond the migration

Once the architecture is stable, strategies are added one at a time, each
independently testable and each a deliberate addition — not implemented
in a batch before the plumbing exists to evaluate them fairly.

- **V2** — Pluggable strategy interface, conversation/session isolation,
  a real tokenizer (not just the word-count heuristic), an offline CLI
  harness that replays fixed conversations through a chosen strategy
  without a browser involved.
- **V3** — A small, deliberately-not-huge set of additional strategies
  (semantic retrieval via embeddings, one hybrid/adaptive policy) plus a
  reproducible benchmark suite (synthetic long conversations with planted
  facts and scripted probes) and a results dashboard.
- **Research version** — A published, reproducible empirical comparison
  across strategies, written up as a technical report. Realistic framing:
  a rigorous empirical/systems contribution, not a novel-algorithm paper.
- **Open-source version** — Docs, `CONTRIBUTING.md`, CI, packaging. Timed
  alongside V2, not after, since the pluggable strategy interface is what
  makes outside contributions ("add a strategy") tractable in the first
  place.
- **Production version** — Auth, multi-tenant conversations, durable
  storage, observability, rate limiting. Deliberately last: production
  hardening trades away the flexibility to swap strategies quickly, which
  is the opposite of what the research/experimentation phases need.

## Priority note

Conversation/session isolation (a `conversation_id` on messages, so
independent experiment runs don't share state) is a prerequisite for
running comparable strategy trials at all. It should land early in V2,
not be deferred as a "nice to have" — everything past it assumes it
exists.
