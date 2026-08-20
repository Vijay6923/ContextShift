"""
OpenRouterProvider construction and configuration tests. The HTTP-level
behavior (retries, streaming parsing, error handling) is structurally
identical to GroqProvider's, covered in test_llm_characterization.py;
these tests cover what is OpenRouter-specific.
"""
import pytest

from contextshift.llm.openrouter import DEFAULT_BASE_URL, DEFAULT_MODEL, OpenRouterProvider


def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        OpenRouterProvider(api_key="")


def test_defaults():
    provider = OpenRouterProvider(api_key="test-key")
    assert provider._model == DEFAULT_MODEL
    assert provider._base_url == DEFAULT_BASE_URL
    assert DEFAULT_MODEL == "meta-llama/llama-3.1-8b-instruct"
    assert DEFAULT_BASE_URL == "https://openrouter.ai/api/v1/chat/completions"


def test_model_and_base_url_are_overridable():
    provider = OpenRouterProvider(api_key="test-key", model="a-different-model", base_url="https://example.com")
    assert provider._model == "a-different-model"
    assert provider._base_url == "https://example.com"


def test_attribution_headers_omitted_by_default():
    provider = OpenRouterProvider(api_key="test-key")
    headers = provider._headers()
    assert "HTTP-Referer" not in headers
    assert "X-Title" not in headers


def test_attribution_headers_sent_when_configured():
    provider = OpenRouterProvider(api_key="test-key", site_url="https://myapp.example", app_name="MyApp")
    headers = provider._headers()
    assert headers["HTTP-Referer"] == "https://myapp.example"
    assert headers["X-Title"] == "MyApp"


def test_never_reads_application_config():
    # OpenRouterProvider must have zero dependency on config.Config -- see
    # docs/decisions/0001-library-independence-and-adapter-placement.md.
    import inspect

    import contextshift.llm.openrouter as openrouter_module

    source = inspect.getsource(openrouter_module)
    assert "import config" not in source
    assert "from config" not in source
