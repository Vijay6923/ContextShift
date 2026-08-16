# Contributing to ContextShift

Issues and pull requests are welcome. This document covers how to get a
development environment running, what's expected of a change, and where
to look before proposing something new.

## Before you start

For anything beyond a small fix (a new `ContextStrategy`, a new
`Tokenizer` backend, a change to a public interface), open an issue
first describing what you'd like to change and why. It's the fastest
way to find out whether an idea fits the architecture before you invest
time in a pull request — see [`docs/architecture.md`](docs/architecture.md)
and [`docs/philosophy.md`](docs/philosophy.md) for what the library is
(and deliberately isn't) trying to be, and
[`docs/decisions/`](docs/decisions/) for why specific past choices were
made, including alternatives that were considered and rejected. A
proposal for a new strategy specifically should use the
["New strategy proposal" issue template](.github/ISSUE_TEMPLATE/new_strategy_proposal.md).

## Development setup

```bash
git clone https://github.com/Vijay6923/ContextShift.git
cd ContextShift
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
pip install -r requirements-dev.txt
```

This installs `contextshift` itself (editable) plus `pytest`,
`pytest-cov`, `ruff`, `mypy`, and the `tiktoken`/`anthropic` extras —
everything needed to run the full test suite, including
`TiktokenTokenizer`/`AnthropicTokenizer`'s own tests and the example
Flask app's own tests (its core dependencies are already part of
`contextshift`'s own `[project.dependencies]`; see
[`pyproject.toml`](pyproject.toml)).

## Running the checks

```bash
pytest                      # full suite: contextshift/ + examples/flask-chat/
pyflakes contextshift/ tests/ examples/flask-chat/app.py examples/flask-chat/adapters.py examples/flask-chat/models.py examples/flask-chat/config.py
ruff check .
mypy --strict contextshift/
```

All four are expected to pass clean before a pull request is opened.
`mypy --strict` is scoped to `contextshift/`
only — the example Flask
app is not held to the same typing standard, since it predates the
library and exists to demonstrate usage, not to showcase typing
discipline.

## What a good pull request looks like

- **Tests included, not just added coverage.** A new `ContextStrategy`
  needs direct behavioral tests (see any existing
  `tests/test_strategies_*.py` for the expected shape) and should run
  cleanly through `contextshift.benchmark.needle`'s deterministic tier
  against the existing fixture suite
  (`tests/fixtures/conversations/`) without modification.
- **An ADR for anything architecturally significant** — a new public
  interface, a new cross-subpackage dependency, or a decision that
  would be costly to reverse later. See any file in
  [`docs/decisions/`](docs/decisions/) for the expected format
  (Status / Context / Decision / Consequences), and its `README.md`
  for when a decision earns a record versus when it doesn't.
- **No speculative abstraction.** A field, method, or export should
  trace back to a concrete, existing consumer in this repository —
  see [`docs/philosophy.md`](docs/philosophy.md)'s design principles.
  If you're adding a `Protocol` implementation, it should conform
  structurally (no inheritance from a ContextShift base class
  required) — see [ADR 0005](docs/decisions/0005-protocol-over-abc.md).
- **Dependencies flow one direction.** `contextshift/` never imports
  from `examples/`; within the library, every subpackage depends only
  on what its own job requires — see
  [`docs/architecture.md`](docs/architecture.md)'s dependency rules
  before adding a new cross-subpackage import.

## Commit messages and pull request descriptions

Explain *why*, not just *what* — the diff already shows what changed.
If a change fixes a specific failure mode, name it; if it's adding a
new capability, say what concrete use case motivated it.

## Reporting bugs or requesting features

Use the appropriate [issue template](.github/ISSUE_TEMPLATE/) — bug
report, feature request, or new-strategy proposal. A minimal
reproduction (a short conversation + budget + strategy that shows the
problem) is the single most useful thing you can include in a bug
report.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
By participating, you're expected to uphold it.

## Security

Do not open a public issue for a security vulnerability — see
[`SECURITY.md`](SECURITY.md) for how to report one privately.
