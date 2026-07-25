from conftest import seed_message
from models import Message


def test_summarize_with_no_messages_reports_not_enough(client):
    response = client.post("/summarize")

    assert response.status_code == 200
    assert "Not enough messages" in response.get_json()["message"]


def test_summarize_with_one_message_reports_not_enough(client, app_ctx):
    seed_message("user", "hi")

    response = client.post("/summarize")

    assert response.status_code == 200
    assert "Not enough messages" in response.get_json()["message"]


def test_summarize_archives_originals_and_stores_summary(client, app_ctx, monkeypatch):
    monkeypatch.setattr("utils.summarizer.call_groq", lambda messages, max_tokens=512: "This is a summary.")

    seed_message("user", "what's the capital of France?")
    seed_message("assistant", "Paris.")

    response = client.post("/summarize")
    payload = response.get_json()

    assert response.status_code == 200
    assert "Successfully summarized the entire conversation (2 messages)" in payload["message"]
    assert payload["summary"] == "[SUMMARY] This is a summary."

    originals = Message.query.filter(Message.role.in_(["user", "assistant"])).all()
    assert all(m.is_archived for m in originals)

    summaries = Message.query.filter_by(role="system").all()
    assert len(summaries) == 1
    assert summaries[0].content == "[SUMMARY] This is a summary."
    assert summaries[0].is_archived is False


def test_summarize_excludes_pinned_messages(client, app_ctx, monkeypatch):
    monkeypatch.setattr("utils.summarizer.call_groq", lambda messages, max_tokens=512: "Summary.")

    seed_message("user", "pinned question", is_pinned=True)
    seed_message("assistant", "pinned answer", is_pinned=True)
    seed_message("user", "regular question")
    seed_message("assistant", "regular answer")

    client.post("/summarize")

    pinned = Message.query.filter_by(is_pinned=True).all()
    assert all(not m.is_archived for m in pinned)
