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
- [x] **Step V — Vision capability** (ADR 0011 Phase implementation status).
      Extracted `analyze_image_with_gemini`'s AI-calling half into
      `contextshift.vision` (`VisionProvider` protocol +
      `GeminiVisionProvider`), consuming
      `contextshift.ingestion.prepare_image_for_vision`'s output --
      resolving the module location ADR 0010 deliberately left open.
      `/upload`'s image branch now calls `adapters.build_vision_provider()`.
      `analyze_image_with_gemini` is deleted from `utils/file_processor.py`.
- [x] **Step 9, revised** — Originally planned to delete
      `utils/token_manager.py`, `utils/context_builder.py`,
      `utils/summarizer.py`, and `utils/file_processor.py` outright. The
      v1.0 cleanup pass examined this directly and found the original
      premise wrong: every one of those files is still imported, by
      name, as the "legacy" side of a characterization test that
      remains genuinely protective --
      `tests/test_strategy_characterization.py`,
      `tests/test_tokenizer_characterization.py`,
      `tests/test_llm_characterization.py`,
      `tests/test_summarization_characterization.py`, and
      `tests/test_ingestion_characterization.py` all still compare the
      current library against these files' independently-written
      behavior. Deleting them would delete that protection, not just
      dead weight. What *was* dead weight and safely removed instead:
      `tests/test_context_builder.py` and `tests/test_token_manager.py`
      -- standalone tests of the legacy modules in isolation, fully
      redundant with direct tests of the current strategies/tokenizer
      plus the characterization tests above. `utils/` stays,
      indefinitely, as characterization fixtures -- not scaffolding
      waiting to be deleted.
- [x] **Step 10** — `contextshift/` packaged as installable
      (`pyproject.toml`, `pip install -e .`).

## Beyond the migration

The migration above extracted the library. What follows -- turning it
into a framework with an orchestration API, multiple strategies, and a
benchmark -- happened as a separate, explicitly-reviewed track ("Framework
v2"), recorded in
[`decisions/0011-framework-v2-design-review.md`](decisions/0011-framework-v2-design-review.md)
and
[`decisions/0012-strategy-framework-and-benchmark-review.md`](decisions/0012-strategy-framework-and-benchmark-review.md).
This section is kept short and points there rather than duplicating it,
since ADR 0012 in particular is the current, load-bearing statement of
what's done and what's deliberately not built yet.

**Done**, via that track rather than this one: `ContextManager`
(orchestration), a second and third `ContextStrategy`
(`RecencyStrategy`, `SlidingWindowStrategy`), `VisionProvider` +
`GeminiVisionProvider`, a public `contextshift.testing.FakeLLMProvider`,
and `contextshift.benchmark` (deterministic strategy comparison).

**Not built, deliberately, per ADR 0012** — semantic retrieval,
embeddings, vector stores, a strategy/provider registry, a generic
`StrategyPipeline`, session/memory persistence, a dataset or evaluation
framework, LLM-as-judge scoring, telemetry. Each has a named condition
in ADR 0012 that would justify building it; none has been triggered.

**Next, per ADR 0012's roadmap**: `HybridStrategy`, composed from the
existing strategies rather than a new algorithm, plus whatever
comparisons run against the current three strategies concretely
surface as missing (e.g. a more accurate tokenizer, or a second
provider) -- not pre-built ahead of that evidence.

Conversation/session isolation (a `conversation_id` on messages, so
independent experiment runs don't share state) remains a real
prerequisite for benchmarking against real captured conversations
rather than synthetic fixtures, but has not been needed yet -- the
current benchmark framework takes a fixed message list directly, with
no database involved.
