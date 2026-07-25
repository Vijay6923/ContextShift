"""
GroqProvider construction and configuration tests. Behavior that requires
mocking HTTP calls (retries, streaming parsing, error handling) is
covered in test_llm_characterization.py, alongside the direct comparison
against the legacy implementation.
"""
import pytest

from contextshift.llm.groq import DEFAULT_BASE_URL, DEFAULT_MODEL, GroqProvider


def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        GroqProvider(api_key="")


def test_defaults_match_legacy_configuration():
    provider = GroqProvider(api_key="test-key")
    assert provider._model == DEFAULT_MODEL
    assert provider._base_url == DEFAULT_BASE_URL
    assert DEFAULT_MODEL == "llama-3.1-8b-instant"
    assert DEFAULT_BASE_URL == "https://api.groq.com/openai/v1/chat/completions"


def test_model_and_base_url_are_overridable():
    provider = GroqProvider(api_key="test-key", model="a-different-model", base_url="https://example.com")
    assert provider._model == "a-different-model"
    assert provider._base_url == "https://example.com"


def test_never_reads_application_config():
    # GroqProvider must have zero dependency on config.Config -- see
    # docs/decisions/0001-library-independence-and-adapter-placement.md.
    # A real assertion, not just a lint check: importing and constructing
    # it must not require config.py to exist or GROQ_API_KEY to be set in
    # the environment at all.
    import inspect

    import contextshift.llm.groq as groq_module

    source = inspect.getsource(groq_module)
    assert "import config" not in source
    assert "from config" not in source
