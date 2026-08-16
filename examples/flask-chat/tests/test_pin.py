from datetime import datetime, timedelta

from conftest import seed_message
from models import Message

_BASE = datetime(2026, 1, 1, 12, 0, 0)


def test_pin_nonexistent_message_returns_404(client):
    response = client.post("/pin/999999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Message not found"


def test_pin_user_message_cascades_to_paired_assistant_reply(client, app_ctx):
    user_msg = seed_message("user", "question", timestamp=_BASE)
    assistant_msg = seed_message("assistant", "answer", timestamp=_BASE + timedelta(seconds=1))

    response = client.post(f"/pin/{user_msg.id}")

    assert response.status_code == 200
    assert response.get_json()["is_pinned"] is True
    assert Message.query.get(user_msg.id).is_pinned is True
    assert Message.query.get(assistant_msg.id).is_pinned is True

    unpin_response = client.post(f"/pin/{user_msg.id}")
    assert unpin_response.get_json()["is_pinned"] is False
    assert Message.query.get(user_msg.id).is_pinned is False
    assert Message.query.get(assistant_msg.id).is_pinned is False


def test_pin_assistant_message_does_not_cascade(client, app_ctx):
    user_msg = seed_message("user", "question", timestamp=_BASE)
    assistant_msg = seed_message("assistant", "answer", timestamp=_BASE + timedelta(seconds=1))

    client.post(f"/pin/{assistant_msg.id}")

    assert Message.query.get(assistant_msg.id).is_pinned is True
    assert Message.query.get(user_msg.id).is_pinned is False
