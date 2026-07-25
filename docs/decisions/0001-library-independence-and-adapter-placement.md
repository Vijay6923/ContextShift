# 0001 — Library independence and adapter placement

## Status

Accepted.

## Context

ContextShift's stated goal is for the context-management logic to become
a standalone Python library that's useful to another developer or
researcher even if the Flask demo application disappeared entirely. The
existing implementation (`utils/context_builder.py`, `utils/token_manager.py`,
etc.) doesn't satisfy that: it operates directly on SQLAlchemy `Message`
ORM instances and imports the Flask app's `Config` class, so none of it
can be imported, tested, or reused without a live Flask app context.

Two things needed deciding before extraction could start: (1) where the
line between "library" and "application" actually falls, and (2) where
the translation code between the two sides of that line should live.

## Decision

1. **`contextshift/` will have zero dependency on Flask, SQLAlchemy, or
   any other application-layer framework**, enforced as a hard rule, not
   a guideline. It defines its own plain domain types (`core.Message`,
   `core.TokenBudget`) rather than accepting ORM instances or a Flask
   `Config` object.
2. **Translation between the application's SQLAlchemy `Message` and the
   library's `core.Message` is application-layer code (an "adapter"),
   not library code.** An adapter's entire purpose is to know about both
   representations; code that knows about both sides of a boundary cannot
   live on the side that's supposed to know about neither. The adapter
   will be introduced at the migration step that actually needs it (the
   `app.py` cutover), not scaffolded speculatively ahead of time.
3. **Corollary:** `app.py`, `models.py`, and `config.py` stay at the repo
   root rather than being relocated into a `server/` subdirectory. The
   dependency-direction rule is about what imports what, not about
   directory layout — and relocating them would touch the Vercel
   deployment path (`api/index.py`'s `sys.path` assumption, `vercel.json`'s
   build `src`) for no architectural benefit. If a physical reorganization
   is wanted later for tidiness, it is a separate, low-priority, isolated
   decision, not a consequence of this one.

## Consequences

**Easier:** `contextshift/` can be unit-tested with plain Python objects,
no Flask app context or database required (demonstrated directly in the
Step 0 test suite's `test_context_builder.py`/`test_token_manager.py`,
written before this extraction even began, to characterize the target
behavior). It can eventually be imported by a CLI, a notebook, or another
project's code without dragging in Flask or SQLAlchemy as transitive
dependencies.

**Harder:** every route in `app.py` that currently passes ORM instances
straight into context-management functions will need to route through an
adapter at the cutover step, which is one extra hop rather than a direct
call. This is treated as acceptable friction in exchange for the
independence goal, not an oversight to optimize away later.

**Forecloses:** library code reaching into `flask.g`, `flask.request`, or
SQLAlchemy session state as a shortcut — any future contributor doing this
would be violating an explicit, recorded rule, not just an implicit
convention.
