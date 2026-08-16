"""
Benchmarking ContextStrategy implementations, in two tiers.

**Deterministic tier (default, no network, runs in CI):**

- `run_benchmark()` -- messages kept/discarded, tokens kept/discarded,
  percentage retained, selection latency, for a single conversation.
  This alone is tautological for anything a strategy's own definition
  already implies (a strategy defined as "keep 10 messages" reporting
  that it kept 10 messages is not a finding).
- `run_needle_benchmark()` -- the non-tautological question: across a
  suite of hand-annotated fixtures (contextshift.benchmark.probes),
  did the messages a real question actually depends on survive
  selection? Still zero network calls -- "load-bearing" is decided
  once, by a human, when the fixture is written, not inferred here.

**Opt-in tier (contextshift.benchmark.judge, real model calls):**

- `run_judged_benchmark()` -- the question needle retention is a
  proxy for: given what a strategy selected, does a real model
  actually answer the probe correctly? Requires a caller to supply an
  `LLMProvider` and a `Judge` explicitly; nothing calls a network
  unless asked to. Reports mean and standard deviation over repeated
  runs, never a single number, since model answers aren't
  deterministic.

Depends on contextshift.strategies (the ContextStrategy protocol it
runs), contextshift.core (Message, TokenBudget), and, for the opt-in
tier only, contextshift.llm's LLMProvider protocol -- the one new
cross-subpackage dependency the opt-in tier introduces, isolated to
`judge.py` so importing the deterministic tier never pulls in
anything network-capable.

Returns plain Python objects; nothing here prints, logs, or writes
files. to_csv()/to_markdown()/judged_to_markdown() render results as
text -- what a caller does with that text is the caller's decision.
"""
from contextshift.benchmark.judge import (
    Judge,
    JudgedProbeRun,
    JudgedResult,
    SubstringJudge,
    judged_to_markdown,
    run_judged_benchmark,
)
from contextshift.benchmark.needle import ProbeOutcome, evaluate_fixture, run_needle_benchmark
from contextshift.benchmark.probes import ConversationFixture, Probe, load_fixture, load_fixtures
from contextshift.benchmark.runner import BenchmarkResult, run_benchmark, to_csv, to_markdown

__all__ = [
    "BenchmarkResult",
    "run_benchmark",
    "to_csv",
    "to_markdown",
    "Probe",
    "ConversationFixture",
    "load_fixture",
    "load_fixtures",
    "ProbeOutcome",
    "evaluate_fixture",
    "run_needle_benchmark",
    "Judge",
    "SubstringJudge",
    "JudgedProbeRun",
    "JudgedResult",
    "run_judged_benchmark",
    "judged_to_markdown",
]
