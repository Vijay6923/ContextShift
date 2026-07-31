from app import app as flask_app
from models import Message
from fakes import FakeLLMProvider


def test_chat_rejects_empty_message(client):
    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Message cannot be empty"


def test_chat_streams_response_and_persists_messages(client, monkeypatch):
    fake_provider = FakeLLMProvider(stream_chunks=["Hello", " world"])
    monkeypatch.setattr("adapters.build_provider", lambda: fake_provider)

    response = client.post("/chat", json={"message": "hello there"})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "data: Hello" in body
    assert "world" in body
    assert "data: [STATS]" in body

    # Route's own generate() manages its app context internally during
    # streaming; open a fresh one here, after the response is fully
    # consumed, purely to query the persisted result.
    with flask_app.app_context():
        messages = Message.query.order_by(Message.timestamp.asc()).all()
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].content == "hello there"
        assert messages[1].content == "Hello world"
        assert messages[1].token_count > 0


def test_chat_second_turn_sends_first_turn_as_history_through_context_manager(client, monkeypatch):
    # Proves /chat's DB history actually reaches the provider via
    # adapters.build_context_manager() (Framework Phase 2) -- not just
    # that a reply streams back, which the happy-path test above already
    # covers. A wiring mistake (e.g. passing the wrong history, or
    # double-including the new turn) would show up here as an unexpected
    # message list, not as a missing response.
    fake_provider = FakeLLMProvider(stream_chunks=["ok"])
    monkeypatch.setattr("adapters.build_provider", lambda: fake_provider)

    # get_data() forces the streaming generator to fully run, including
    # its post-stream DB commit -- without it, the assistant reply from
    # the first turn is never persisted for the second turn to see.
    client.post("/chat", json={"message": "first turn"}).get_data()
    client.post("/chat", json={"message": "second turn"}).get_data()

    assert len(fake_provider.stream_calls) == 2
    second_call_messages, _ = fake_provider.stream_calls[1]
    contents = [m.content for m in second_call_messages]

    assert contents.count("first turn") == 1
    assert contents.count("ok") == 1
    assert contents.count("second turn") == 1
    assert contents.index("first turn") < contents.index("ok") < contents.index("second turn")
