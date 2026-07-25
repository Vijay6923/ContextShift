from conftest import seed_message
from models import Message


def test_index_archives_all_existing_messages(client, app_ctx):
    seed_message("user", "hi", is_archived=False)
    seed_message("assistant", "hello", is_archived=False, is_pinned=True)

    response = client.get("/")

    assert response.status_code == 200
    remaining_active = Message.query.filter_by(is_archived=False).count()
    assert remaining_active == 0


def test_reset_archives_all_active_messages(client, app_ctx):
    seed_message("user", "hi", is_archived=False)
    seed_message("assistant", "hello", is_archived=False)

    response = client.post("/reset")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Conversation reset"
    assert Message.query.filter_by(is_archived=False).count() == 0
