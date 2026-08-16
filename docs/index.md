# ContextShift

A Python framework for context engineering: pluggable, benchmarkable
strategies for deciding what an LLM sees under a token budget.

This site hosts ContextShift's design documentation — architecture,
philosophy, versioning policy, roadmap, and every Architecture Decision
Record. For installation, the quick start, the strategy comparison
table, and the needle-retention benchmark results, see the
[project README on GitHub](https://github.com/Vijay6923/ContextShift#readme).

## Where to start

- **New to the project?** Start with [Philosophy](philosophy.md) — what
  ContextShift is for, and what it deliberately doesn't do.
- **Contributing or extending it?** [Architecture](architecture.md)
  covers the current layer structure and dependency rules;
  [Decisions](decisions/README.md) explains *why* each one was made,
  including alternatives that were considered and rejected.
- **Evaluating whether a benchmark claim is real?**
  [Benchmarks](benchmarks/README.md) has the committed, literal output
  of every benchmark suite, regenerable with one command.
- **Wondering how this compares to existing work?**
  [Prior Art](prior-art.md) names what this builds on and departs from
  — needle-in-a-haystack, RULER, LoCoMo, LongMemEval, Mem0, Letta, and
  more.
- **Wondering what's stable to depend on?** [Versioning](versioning.md)
  states exactly what's protocol-stable pre-1.0 and what a `1.0.0`
  release will commit to.
- **Curious what's next?** [Roadmap](roadmap.md) tracks what's done and
  what's planned.
