# 0016 — Repository shape for outside readers

## Status

Accepted.

## Context

Before this change, the repository root mixed two things a stranger
cloning it needs to tell apart immediately: the library
(`contextshift/`) and one particular application built on it (`app.py`,
`adapters.py`, `models.py`, `config.py`, `templates/`, `static/`,
`vercel.json`, `api/`, plus that application's own `requirements.txt`
and `.env.example`). A first-time reader landing on the root saw a
Flask app's files interleaved with a library's files, with nothing
structurally distinguishing "this is the thing you'd install" from
"this is one example of using it." `utils/` compounded this: a
pre-refactor implementation kept only so characterization tests could
assert the new library matches old behavior, sitting at the root as if
it were live production code, when nothing in `app.py` or `adapters.py`
had imported it for several phases already.

## Decision

**The Flask demo moved to `examples/flask-chat/`, wholesale — code,
routes, templates, static assets, deployment config, its own
`requirements.txt`, `.env.example`, and its own route-level tests
(`examples/flask-chat/tests/`).** It gets a README of its own
(`examples/flask-chat/README.md`) covering exactly what a reader who
wants to run *this specific application* needs — not the library.

**`utils/` moved to `tests/fixtures/legacy/`, unambiguously scoped as a
test fixture rather than application code.** Every internal cross-import
(`from config import Config`, `from utils import token_manager`)
updated from implicit root-relative imports to explicit
`tests.fixtures.legacy.*` imports — Config itself was trimmed to a
minimal, dependency-free `tests/fixtures/legacy/config.py` holding only
the six constants (`GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_BASE_URL`,
`MAX_TOKENS`, `RECENT_BUFFER`, `TOKEN_SAFETY_MARGIN`) the legacy fixture
modules actually read, rather than dragging the real
`examples/flask-chat/config.py` (Flask, SQLAlchemy, dotenv) into the
library's own test tree. The six root-level characterization tests
(`tests/test_*_characterization.py`) stayed in place — they compare
`contextshift/` against `tests/fixtures/legacy/`, both of which now
live under the same root-level tree, and were updated only to import
from the fixture's new path.

**A hard split emerged between two test suites, run independently or
together.** `tests/` (root) needs nothing beyond
`pip install -e ".[dev]"` — no Flask, no SQLAlchemy, no database — the
same "network-free, dependency-light" property the library itself has
always had. `examples/flask-chat/tests/` needs the Flask app's own
`requirements.txt`. A plain `pytest` from the repository root still
collects and runs both together (406 tests, unchanged pass count from
before this move), since `pyproject.toml`'s core dependencies already
include Flask/Flask-Cors/Flask-SQLAlchemy/python-dotenv — but a
contributor who only cares about the library never has to notice the
example app's tests exist.

**`examples/flask-chat/requirements.txt` gained one line:
`-e ../..`.** Before this move, `app.py` sat directly beside
`contextshift/`, and Python's automatic script-directory sys.path entry
was enough to resolve `import contextshift` with no separate install
step. One directory deeper, that's no longer true — verified directly
(not assumed) by installing into a genuinely fresh virtualenv and
confirming `import app` fails without this line and succeeds with it,
with every Flask route registering correctly afterward. `-e ../..`
resolves relative to wherever `pip install -r requirements.txt` is run
*from*, not relative to the requirements file itself — the example's
README says explicitly to run that command from inside
`examples/flask-chat/`, not the repository root, because of this.

**`examples/flask-chat/tests/conftest.py` gained an explicit
`sys.path` insertion for its own parent directory**, for the same
underlying reason: pytest's rootdir-insertion adds
`examples/flask-chat/tests/` to `sys.path` (no `__init__.py` there),
which is one directory short of where `app.py`, `models.py`,
`config.py`, and `adapters.py` actually live now. Every sibling test
module in that directory depends on this one insertion happening first,
which is why it's in `conftest.py` (pytest always imports it before any
test module) rather than repeated per file.

## Consequences

**Easier:** a stranger's first `ls` at the repository root now shows
`contextshift/, tests/, docs/, examples/`, plus packaging files —
matching this ADR's own exit criterion, that a stranger understands
what this repository is within thirty seconds. The library's own test
suite has zero Flask/database dependency, verifiable directly: nothing
in `tests/` (root) imports `flask`, `flask_sqlalchemy`, or anything
under `examples/`.

**Harder:** running the example app now takes one more command
(`pip install -r requirements.txt` from *inside*
`examples/flask-chat/`, not the root) than it did when `app.py` sat at
the root and resolved `contextshift` implicitly. This is documented
explicitly in `examples/flask-chat/README.md` rather than left for a
reader to discover through a traceback.

**Forecloses:** treating `utils/` as a second, parallel implementation
a contributor might mistake for something still in use.
`tests/fixtures/legacy/__init__.py` states directly that nothing in
`contextshift/` or `examples/` imports it.
