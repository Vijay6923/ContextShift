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
- [ ] **Step 5** — Port the Groq REST client → `llm/groq.py` behind an
      `LLMProvider` interface.
- [ ] **Step 6** — Port `summarize_messages` → `summarization/`, built on
      `llm/`.
- [ ] **Step 7** — Port PDF/vision extraction → `ingestion/`.
- [ ] **Step 8** — Cutover: wire `app.py` to `contextshift/` one route at a
      time (8a–8f), via a new application-layer adapter module.
- [ ] **Step 9** — Delete the now-dead `utils/` package.
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
