"""
Benchmarking ContextStrategy implementations.

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

Depends on contextshift.strategies (the ContextStrategy protocol it
runs) and contextshift.core (Message, TokenBudget) -- nothing else.

Returns plain Python objects; nothing here prints, logs, or writes
files. to_csv()/to_markdown() render results as text -- what a caller
does with that text is the caller's decision.
"""
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
]
