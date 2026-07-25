from datetime import datetime, timedelta

from conftest import seed_message
from models import Message

_BASE = datetime(2026, 1, 1, 12, 0, 0)


def _seed_sequential(n, prefix="msg"):
    for i in range(n):
        seed_message("user", f"{prefix} {i}", timestamp=_BASE + timedelta(seconds=i))


def test_prune_noop_when_six_or_fewer_active_messages(client, app_ctx):
    _seed_sequential(6)

    response = client.post("/prune")

    assert response.status_code == 200
    assert "No messages to prune" in response.get_json()["message"]
    assert Message.query.filter_by(is_archived=False).count() == 6


def test_prune_archives_oldest_beyond_recent_six(client, app_ctx):
    _seed_sequential(8)

    response = client.post("/prune")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Pruned 2 messages"

    active = Message.query.filter_by(is_archived=False).order_by(Message.timestamp.asc()).all()
    archived = Message.query.filter_by(is_archived=True).order_by(Message.timestamp.asc()).all()

    assert [m.content for m in archived] == ["msg 0", "msg 1"]
    assert [m.content for m in active] == [f"msg {i}" for i in range(2, 8)]


def test_prune_never_touches_pinned_messages(client, app_ctx):
    seed_message("user", "pinned", is_pinned=True, timestamp=_BASE)
    _seed_sequential(8, prefix="unpinned")

    client.post("/prune")

    pinned = Message.query.filter_by(is_pinned=True).one()
    assert pinned.is_archived is False
