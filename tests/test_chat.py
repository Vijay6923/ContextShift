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
