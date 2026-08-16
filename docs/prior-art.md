# Prior art

ContextShift's needle-retention benchmark, its `SummarizationStrategy`,
and the cache-awareness work named on the [roadmap](roadmap.md) all sit
in a space with real, active prior work. This page names what
ContextShift builds on, what already exists that it deliberately
doesn't try to replace, and where it actually differs — so a reader
familiar with this literature can place the project accurately instead
of wondering whether it's aware of it.

## Long-context and retrieval evaluation

**[Needle in a Haystack](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)**
(Greg Kamradt, 2023) is the origin of the evaluation idea ContextShift's
needle-retention benchmark borrows its name and its central question
from: insert a specific fact into a large body of text, then check
whether it can be retrieved. Kamradt's version tests a *model's* ability
to retrieve a fact from a long context window at inference time, plotted
as a heatmap across context length and depth.

**[RULER](https://arxiv.org/abs/2404.06654)** (Hsieh et al., NVIDIA,
2024) generalizes needle-in-a-haystack into a fuller synthetic
benchmark — multiple needles, multi-hop tracing, and aggregation tasks —
specifically to catch models that accept a long context window without
actually using all of it effectively.

**ContextShift's needle-retention benchmark asks a narrower, different
question at a different point in the pipeline.** It does not test
whether a *model* can find a fact in a long context — it tests whether
a *context-selection strategy* keeps the specific messages a later
question depends on, before the model ever sees anything. No model
call is required to get a number (see
[ADR 0013](decisions/0013-needle-retention-benchmark.md)); the "needle"
is a set of message indices a human annotated in advance, not a fact
the benchmark asks a model to recall. It's a much smaller, much cheaper
sanity check that answers a different question: not "can the model use
its context window," but "did my own truncation/summarization logic
hand the model the right subset of messages in the first place." A
project that has verified its strategy preserves load-bearing messages
still needs RULER or needle-in-a-haystack-style evaluation to know
whether the model it's calling can actually use what survived — the two
questions are complementary, not substitutes for each other.

## Long-horizon conversational memory benchmarks

**[LoCoMo](https://arxiv.org/abs/2402.17753)** (Maharana et al., 2024)
evaluates long-term conversational memory in LLM agents via
LLM-generated, human-refined multi-session dialogues (50 dialogues,
up to 35 sessions and ~300 turns each, ~9K tokens on average,
multimodal) grounded in persona profiles and temporal event graphs,
testing single-hop, multi-hop, temporal, and open-domain question
answering against that history.

**[LongMemEval](https://arxiv.org/abs/2410.10813)** (Wu et al., ICLR
2025) benchmarks chat assistants on five long-term memory abilities —
information extraction, multi-session reasoning, temporal reasoning,
knowledge updates, and abstention — across 500 curated questions, and
reports that commercial assistants and long-context LLMs alike show a
measurable accuracy drop sustaining memory across long interactions.

**[LoCoEval](https://arxiv.org/abs/2603.06358)** (2026) is closer to
ContextShift's actual domain than the two above: a benchmark
specifically for long-horizon *conversational context management* in
repository-oriented development, evaluating context-management methods
directly (not just model recall) via an LLM-driven dynamic evaluation
pipeline.

**[AMemGym](https://arxiv.org/abs/2603.01966)** (2026) is an
interactive, on-policy evaluation environment for memory-driven
personalization in long-horizon conversations, using LLM-simulated
users with structured, evolving latent state to test memory systems
under realistic interaction dynamics rather than a fixed, static
transcript.

**All four are research benchmarks: papers with an accompanying
evaluation harness or dataset, typically requiring real model calls
(often several, to generate or grade the interaction) and, for LoCoEval
and AMemGym, an LLM-driven pipeline to produce the evaluation scenarios
themselves.** ContextShift's fixture suite is the opposite shape on
purpose: a small, fixed, hand-authored set of conversations (see
[ADR 0013](decisions/0013-needle-retention-benchmark.md) for why
they're authored before any strategy runs against them), checkable with
zero model calls, meant to run in CI on every commit rather than as a
standalone research evaluation run occasionally against a new model
release. ContextShift is a pip-installable library with a benchmark
built in, not a benchmark with a reference implementation attached —
a real difference in what each project is *for*, not a claim that one
approach supersedes the other. A project should still reach for
LongMemEval, LoCoMo, LoCoEval, or AMemGym when the question is "how
good is this system's memory," which needle retention deliberately
doesn't try to answer.

## Cache-aware context management

**[TokenPilot](https://arxiv.org/abs/2606.17016)** (2026) is the direct
motivation for the `CacheAwareStrategy` named as future work on the
[roadmap](roadmap.md), not yet built. It manages LLM agent context at
two granularities — ingestion-time compaction to stabilize the prompt
prefix, and lifecycle-aware eviction that only removes a context
segment once its task relevance has genuinely expired — specifically to
avoid invalidating a provider's prompt cache, reporting 56–61% cost
reduction versus naive pruning/eviction.

That cost sensitivity comes directly from how providers price caching:
[Anthropic's prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
and [OpenAI's prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
both price a cache hit far below a cache miss, and both require the
cached *prefix* of a request to stay byte-identical across calls to hit
the cache at all. Every `ContextStrategy` shipped in ContextShift today
mutates that prefix on every turn — pruning from the front (`RecencyStrategy`,
`SlidingWindowStrategy`, `PinnedRecencyStrategy`) or replacing a whole
block with a fresh summary (`SummarizationStrategy`) changes exactly the
bytes a cache lookup keys on. A `CacheAwareStrategy` would need to prune
or compress in a way that preserves a stable prefix — a genuinely
different constraint from anything the current four strategies
optimize for, which is why it's scoped as a future strategy rather than
a change to an existing one.

## Adjacent tools: memory backends, not context-selection strategies

**[Mem0](https://github.com/mem0ai/mem0)** is an open-source (Apache
2.0) memory layer: after each interaction it extracts durable facts,
stores them (a vector store, Qdrant by default, plus Postgres for
history), and retrieves relevant ones on a later call. It owns
persistence and extraction — deciding what's worth remembering across
sessions and where it lives.

**[LangChain](https://github.com/langchain-ai/langchain)'s** classic
memory classes (`ConversationBufferMemory`,
`ConversationSummaryMemory`, and similar) were deprecated as of
LangChain v0.3.1 and are scheduled for removal, replaced by
LangGraph's checkpointer (in-thread, short-term persistence) and
`BaseStore` (cross-thread, long-term persistence) — memory as one part
of a much larger agent-orchestration framework, not a standalone,
benchmarked concern.

**[Letta](https://github.com/letta-ai/letta)** (formerly
**[MemGPT](https://arxiv.org/abs/2310.08560)**, Packer et al., UC
Berkeley, 2023) applies an OS-inspired virtual-memory model to agent
context — main context, recall storage, archival storage — with the
agent itself, via function calling, deciding what to page in and out.
Letta is now a full stateful-agents platform: core/archival memory, a
CLI, an API, a visual editor.

**ContextShift's scope is deliberately narrower than any of these, and
that's the actual distinction, not a claim of superiority.**
[`docs/philosophy.md`](philosophy.md) already states this as a design
principle — "no framework-owned persistence": ContextShift has no
database, no session concept, and doesn't decide what's durable across
conversations. It operates on a message list a caller already has,
deciding what subset of *that* list fits a token budget *this* turn,
and measuring whether that decision was any good. A caller could use
Mem0 or Letta to decide what's worth remembering across sessions and
retrieve it into a message list, and still use ContextShift to decide
what portion of that retrieved list actually fits this turn's budget —
the two are complementary, not competing for the same job.

## What this means for ContextShift's claims

Nothing in this project's README or documentation claims to be the
first benchmark for context management, the first library to compress
conversation history, or a replacement for any of the above. The
specific, checkable claim is narrower: that the messages/tokens-kept
metrics `contextshift.benchmark.run_benchmark()` reports are
tautological on their own (implied by a strategy's configuration, not
a finding), and that `run_needle_benchmark()` — a small, fixed,
model-call-free fixture suite — is a different, non-tautological
measurement of the same strategies. That claim is scoped to this
project's own benchmark, not to the field.
