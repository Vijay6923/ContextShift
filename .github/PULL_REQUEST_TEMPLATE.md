## What does this change, and why?

Explain the motivation — a concrete use case, bug, or gap this closes,
not just a restatement of the diff. Link the issue this addresses, if
any.

## Checklist

- [ ] `pytest` passes locally (full suite: `contextshift/` +
      `examples/flask-chat/`)
- [ ] `ruff check .` is clean
- [ ] `mypy --strict contextshift/` is clean
- [ ] Tests were added or updated for the behavior this changes
- [ ] An ADR was added under `docs/decisions/` if this is architecturally
      significant (a new public interface, a new cross-subpackage
      dependency, or a decision that would be costly to reverse) — see
      `docs/decisions/README.md` for what earns a record
- [ ] `CHANGELOG.md` was updated under `[Unreleased]`

## Anything reviewers should look at closely?

Trade-offs you're unsure about, alternatives you considered and
rejected, or parts of the diff that need more context than the code
alone gives.
