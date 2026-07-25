import io

from models import Message
from fakes import FakeLLMProvider


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


def test_upload_image_happy_path(client, app_ctx, monkeypatch):
    monkeypatch.setattr(
        "utils.file_processor.analyze_image_with_gemini",
        lambda file_bytes, mime_type, user_prompt="": "Image analysis result.",
    )

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
