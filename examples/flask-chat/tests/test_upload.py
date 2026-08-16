import io

from models import Message
from contextshift.testing import FakeLLMProvider


def test_upload_rejects_missing_file(client):
    response = client.post("/upload", data={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "No file provided"


def test_upload_rejects_unsupported_file_type(client):
    data = {"file": (io.BytesIO(b"just text"), "notes.txt")}

    response = client.post("/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "Unsupported file type" in response.get_json()["error"]


def test_upload_rejects_oversized_file(client):
    oversized = io.BytesIO(b"a" * (10 * 1024 * 1024 + 1))
    data = {"file": (oversized, "big.pdf")}

    response = client.post("/upload", data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "File too large" in response.get_json()["error"]


def test_upload_pdf_happy_path(client, app_ctx, monkeypatch):
    monkeypatch.setattr(
        "contextshift.ingestion.extract_text_from_pdf",
        lambda file_bytes: "Extracted PDF text.",
    )
    monkeypatch.setattr(
        "adapters.build_provider",
        lambda: FakeLLMProvider(complete_response="AI response about the PDF."),
    )

    data = {
        "file": (io.BytesIO(b"%PDF-1.4 fake pdf bytes"), "doc.pdf"),
        "prompt": "Summarize this document",
    }

    response = client.post("/upload", data=data, content_type="multipart/form-data")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["response"] == "AI response about the PDF."
    assert "token_stats" in payload

    user_msg = Message.query.filter_by(role="user").one()
    assert "PDF Uploaded: doc.pdf" in user_msg.content
    assert "Summarize this document" in user_msg.content

    assistant_msg = Message.query.filter_by(role="assistant").one()
    assert assistant_msg.content == "AI response about the PDF."


def test_upload_pdf_sends_prior_chat_history_through_context_manager(client, app_ctx, monkeypatch):
    # Proves /upload's PDF path actually reaches the provider through
    # adapters.build_context_manager().chat() (Framework Phase 2), with
    # prior conversation history intact -- not just that a response
    # comes back, which the happy-path test above already covers.
    monkeypatch.setattr(
        "contextshift.ingestion.extract_text_from_pdf",
        lambda file_bytes: "Extracted PDF text.",
    )
    fake_provider = FakeLLMProvider(complete_response="AI response about the PDF.")
    monkeypatch.setattr("adapters.build_provider", lambda: fake_provider)

    client.post("/chat", json={"message": "earlier chat turn"})

    data = {
        "file": (io.BytesIO(b"%PDF-1.4 fake pdf bytes"), "doc.pdf"),
        "prompt": "Summarize this document",
    }
    client.post("/upload", data=data, content_type="multipart/form-data")

    assert len(fake_provider.complete_calls) == 1
    sent_messages, _ = fake_provider.complete_calls[0]
    contents = [m.content for m in sent_messages]

    assert "earlier chat turn" in contents
    assert any("PDF Uploaded: doc.pdf" in c for c in contents)
    assert contents.index("earlier chat turn") < next(
        i for i, c in enumerate(contents) if "PDF Uploaded: doc.pdf" in c
    )


class _FakeVisionProvider:
    def __init__(self, response="Image analysis result."):
        self._response = response
        self.describe_calls = []

    def describe(self, image_bytes, mime_type, prompt=None):
        self.describe_calls.append((image_bytes, mime_type, prompt))
        return self._response


def test_upload_image_happy_path(client, app_ctx, monkeypatch):
    monkeypatch.setattr("adapters.build_vision_provider", lambda: _FakeVisionProvider())

    data = {
        "file": (io.BytesIO(b"fake image bytes"), "photo.png"),
    }

    response = client.post("/upload", data=data, content_type="multipart/form-data")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["response"] == "Image analysis result."

    user_msg = Message.query.filter_by(role="user").one()
    assert "Image Uploaded: photo.png" in user_msg.content

    assistant_msg = Message.query.filter_by(role="assistant").one()
    assert assistant_msg.content == "Image analysis result."


def test_upload_image_passes_none_prompt_through_context_manager_when_no_prompt_given(client, app_ctx, monkeypatch):
    # Proves /upload's image path actually reaches VisionProvider.describe()
    # through adapters.build_vision_provider() (Vision capability), and
    # that an absent user prompt becomes None -- the capability's own
    # default-description signal -- not an empty string.
    fake_vision = _FakeVisionProvider()
    monkeypatch.setattr("adapters.build_vision_provider", lambda: fake_vision)

    data = {"file": (io.BytesIO(b"fake image bytes"), "photo.png")}
    client.post("/upload", data=data, content_type="multipart/form-data")

    _, _, sent_prompt = fake_vision.describe_calls[0]
    assert sent_prompt is None


def test_upload_image_passes_through_custom_prompt(client, app_ctx, monkeypatch):
    fake_vision = _FakeVisionProvider()
    monkeypatch.setattr("adapters.build_vision_provider", lambda: fake_vision)

    data = {
        "file": (io.BytesIO(b"fake image bytes"), "photo.png"),
        "prompt": "What color is this?",
    }
    client.post("/upload", data=data, content_type="multipart/form-data")

    _, _, sent_prompt = fake_vision.describe_calls[0]
    assert sent_prompt == "What color is this?"
