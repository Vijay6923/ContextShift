"""Tests for the VisionProvider protocol itself, independent of any specific implementation."""
from contextshift.vision import GeminiVisionProvider, VisionProvider


def test_gemini_vision_provider_satisfies_vision_provider_protocol():
    assert isinstance(GeminiVisionProvider(api_key="test-key"), VisionProvider)


def test_something_lacking_describe_does_not_satisfy_protocol():
    class NotAProvider:
        pass

    assert not isinstance(NotAProvider(), VisionProvider)
