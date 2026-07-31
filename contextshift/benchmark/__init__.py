"""
Deterministic benchmarking of ContextStrategy implementations.

Runs one or more strategies against the identical (messages, budget)
input and reports what ContextShift already knows about the result --
messages kept/discarded, tokens kept/discarded, percentage retained,
and selection latency. Never calls an LLM, a network, or anything
non-deterministic; nothing here scores answer quality, and nothing
here owns a dataset -- see
docs/decisions/0012-strategy-framework-and-benchmark-review.md
(Sections 4-5) for why those stay out of scope.

Depends on contextshift.strategies (for the ContextStrategy protocol
it runs) and contextshift.core (for Message, TokenBudget) -- the one
new cross-subpackage dependency this module introduces, and a
deliberate one: benchmarking strategies is this module's entire
purpose.

Returns plain Python objects (BenchmarkResult); does not print, log,
or write files itself. to_csv()/to_markdown() render a list of results
as text -- what a caller does with that text (print it, write it to a
file) is the caller's decision.
"""
from contextshift.benchmark.runner import BenchmarkResult, run_benchmark, to_csv, to_markdown

__all__ = ["BenchmarkResult", "run_benchmark", "to_csv", "to_markdown"]
