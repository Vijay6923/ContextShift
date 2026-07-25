from conftest import seed_message


def test_get_messages_returns_active_only_with_stats(client, app_ctx):
    seed_message("user", "hi", token_count=10)
    seed_message("assistant", "hello", token_count=20)
    seed_message("user", "archived one", token_count=999, is_archived=True)

    response = client.get("/messages")
    payload = response.get_json()

    assert response.status_code == 200
    assert len(payload["messages"]) == 2
    assert {m["role"] for m in payload["messages"]} == {"user", "assistant"}

    stats = payload["token_stats"]
    assert stats["current_tokens"] == 30
    assert stats["max_tokens"] == 4000
    assert stats["percentage"] == round(30 / 4000 * 100, 2)
