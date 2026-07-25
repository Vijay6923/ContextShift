"""
Baseline safety net for the pre-refactor Flask app (migration Step 0).

This file must set DATABASE_URL / GROQ_API_KEY *before* `app` (and therefore
`config.Config`) is imported anywhere in the test session, since Config reads
these at class-body evaluation time. pytest imports conftest.py ahead of any
test module, so module-level code here runs first.
"""
import os
import sqlite3
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="contextshift-test-")
_TEST_DB_PATH = f"{_TEST_DB_DIR}/test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
os.environ["FLASK_DEBUG"] = "false"

import pytest  # noqa: E402

from app import app as flask_app  # noqa: E402
from models import Message, db  # noqa: E402

with flask_app.app_context():
    db.create_all()


def _clear_messages_table():
    """
    Clear rows directly via sqlite3, bypassing Flask's app-context stack.

    The /chat route nests `with app.app_context()` inside a
    stream_with_context-wrapped generator (see app.py::generate), which does
    not compose cleanly with Flask 3.x's per-iteration context handling and
    can leave the app-context contextvar stack in a state where a later
    `with flask_app.app_context()` in teardown raises "Popped wrong app
    context". That's an existing quirk in the route under test, not
    something this baseline suite should paper over by avoiding coverage of
    /chat -- so teardown here deliberately never touches Flask's context
    stack at all.
    """
    conn = sqlite3.connect(_TEST_DB_PATH)
    try:
        conn.execute("DELETE FROM message")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    """
    Deliberately not `with flask_app.test_client() as c: ...`. Flask's
    context-preservation feature for that form pushes/pops an app context
    around the whole block (so g/session are inspectable after a request),
    and that pop collides with the /chat route's own nested app-context
    usage inside its stream_with_context generator (see _clear_messages_table
    docstring). None of these tests need post-request g/session inspection,
    so a plain client sidesteps the collision without touching app.py.
    """
    flask_app.config["TESTING"] = True
    _clear_messages_table()

    yield flask_app.test_client()

    _clear_messages_table()


@pytest.fixture
def app_ctx():
    with flask_app.app_context():
        yield flask_app


def seed_message(role, content, token_count=10, is_pinned=False, is_archived=False, timestamp=None):
    """Insert a Message directly via the ORM, bypassing routes, for deterministic fixtures."""
    kwargs = dict(
        role=role,
        content=content,
        token_count=token_count,
        is_pinned=is_pinned,
        is_archived=is_archived,
    )
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    msg = Message(**kwargs)
    db.session.add(msg)
    db.session.commit()
    return msg


def make_message(role, content="x", token_count=10, is_pinned=False):
    """
    Build an in-memory Message, never persisted. context_builder/token_manager
    are pure functions of a message list (no DB queries inside them), so
    tests of that logic need no DB/app context/client fixture at all.
    """
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)
