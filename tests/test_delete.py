from datetime import datetime, timedelta

from conftest import seed_message
from models import Message

_BASE = datetime(2026, 1, 1, 12, 0, 0)


def test_delete_nonexistent_message_returns_404(client):
    response = client.delete("/message/999999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Message not found"


def test_delete_user_message_cascades_to_paired_assistant_reply(client, app_ctx):
    user_msg = seed_message("user", "question", timestamp=_BASE)
    assistant_msg = seed_message("assistant", "answer", timestamp=_BASE + timedelta(seconds=1))

    response = client.delete(f"/message/{user_msg.id}")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Messages deleted"
    assert Message.query.get(user_msg.id).is_archived is True
    assert Message.query.get(assistant_msg.id).is_archived is True


def test_delete_message_without_cascade_target_deletes_only_itself(client, app_ctx):
    assistant_msg = seed_message("assistant", "standalone answer", timestamp=_BASE)

    response = client.delete(f"/message/{assistant_msg.id}")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Message deleted"
    assert Message.query.get(assistant_msg.id).is_archived is True


def test_delete_user_message_does_not_cascade_to_another_user_message(client, app_ctx):
    user_msg = seed_message("user", "first question", timestamp=_BASE)
    other_user_msg = seed_message("user", "second question", timestamp=_BASE + timedelta(seconds=1))

    response = client.delete(f"/message/{user_msg.id}")

    assert response.get_json()["message"] == "Message deleted"
    assert Message.query.get(user_msg.id).is_archived is True
    assert Message.query.get(other_user_msg.id).is_archived is False
