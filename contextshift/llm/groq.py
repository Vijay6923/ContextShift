"""Groq REST API client, ported mechanically from the original application."""
from __future__ import annotations

import json
import time
from collections.abc import Iterator, Sequence

import requests

from contextshift.core import Message

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"

_TEMPERATURE = 0.7
_MAX_RETRIES = 3
_BASE_BACKOFF = 5  # seconds


class GroqProvider:
    """
    An LLMProvider (contextshift.llm.base.LLMProvider) backed by Groq's
    REST API.

    Ported mechanically from the original application's
    utils/summarizer.py (call_groq, call_groq_stream): identical
    retry-on-429 behavior and backoff schedule, identical manual SSE line
    parsing for streaming, identical error messages, identical request
    payload shape (including that only the streaming payload carries a
    "stream" key at all -- the non-streaming payload never did, and this
    port does not unify the two behind one shared builder that would add
    one). Not optimized, hardened, or given a typed exception hierarchy
    during this port -- see
    docs/decisions/0006-llm-provider-interface.md for what was
    deliberately left unchanged and why.

    Owns everything Groq-specific: authentication, the exact request
    payload shape, HTTP transport, and how a streamed response is parsed
    into text chunks. None of this is visible through the LLMProvider
    interface -- code holding an LLMProvider has no way to tell it's
    talking to Groq at all.

    Args:
        api_key: Groq API key. Required, and validated at construction
            time. Unlike the original application, this is not read from
            a global Config -- contextshift never imports application
            configuration directly (see
            docs/decisions/0001-library-independence-and-adapter-placement.md).
            Whatever constructs a GroqProvider (the eventual Flask
            adapter, a CLI, a notebook) supplies it explicitly.
        model: Groq model identifier. Defaults to the model the original
            application always used.
        base_url: Groq's chat-completions endpoint. Defaults to Groq's
            real endpoint; overridable for testing or a future
            self-hosted/proxy deployment.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    def complete(self, messages: Sequence[Message], max_tokens: int = 1024) -> str:
        payload = {
            "model": self._model,
            "messages": self._to_wire_messages(messages),
            "max_tokens": max_tokens,
            "temperature": _TEMPERATURE,
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = requests.post(
                    self._base_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=30,
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                    print(
                        f"[GROQ] Rate limited (attempt {attempt}/{_MAX_RETRIES}). "
                        f"Waiting {retry_after}s before retry..."
                    )
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            except requests.exceptions.RequestException as e:
                print(f"[GROQ API ERROR] attempt {attempt}: {str(e)}")
                if attempt == _MAX_RETRIES:
                    if "429" in str(e):
                        raise Exception("Groq rate limit reached. Please wait a moment and try again.")
                    raise Exception(f"Failed to call Groq API: {str(e)}")
                time.sleep(_BASE_BACKOFF * attempt)

        raise Exception("Groq API request failed after maximum retries.")

    def stream(self, messages: Sequence[Message], max_tokens: int = 1024) -> Iterator[str]:
        payload = {
            "model": self._model,
            "messages": self._to_wire_messages(messages),
            "max_tokens": max_tokens,
            "temperature": _TEMPERATURE,
            "stream": True,
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = requests.post(
                    self._base_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=30,
                    stream=True,
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", _BASE_BACKOFF * attempt))
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue

                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        data_str = line_text[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue

                return  # Success, exit retry loop

            except requests.exceptions.RequestException as e:
                if attempt == _MAX_RETRIES:
                    raise Exception(f"Stream connection failed: {str(e)}")
                time.sleep(_BASE_BACKOFF * attempt)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _to_wire_messages(messages: Sequence[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]
