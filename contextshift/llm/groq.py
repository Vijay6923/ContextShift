"""Groq REST API client."""
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

    Owns everything Groq-specific: authentication, the exact request
    payload shape, HTTP transport, retry-on-429 behavior and backoff
    schedule, and how a streamed response is parsed into text chunks
    (manual SSE line parsing). None of this is visible through the
    LLMProvider interface -- code holding an LLMProvider has no way to
    tell it's talking to Groq at all.

    Deliberately unoptimized and without a typed exception hierarchy --
    errors surface as plain `Exception`/`ValueError` with human-readable
    messages, not a `GroqError`/`RateLimitError` hierarchy. See
    docs/decisions/0006-llm-provider-interface.md for the reasoning.

    Args:
        api_key: Groq API key. Required, and validated at construction
            time. Not read from any global configuration -- contextshift
            never imports application configuration directly (see
            docs/decisions/0001-library-independence-and-adapter-placement.md).
            Whatever constructs a GroqProvider (a Flask adapter, a CLI, a
            notebook) supplies it explicitly.
        model: Groq model identifier. Defaults to `llama-3.1-8b-instant`.
        base_url: Groq's chat-completions endpoint. Defaults to Groq's
            real endpoint; overridable for testing or a self-hosted/proxy
            deployment.
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
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    # A well-formed 200 response can still carry a null (or
                    # otherwise non-string) content field -- a tool-call-only
                    # completion, for instance. str(content) would silently
                    # turn that into the literal text "None"; raising instead
                    # makes the failure visible at the call site rather than
                    # flowing a fake answer into a summary or chat history.
                    raise ValueError(
                        f"Groq API returned a non-string content field ({content!r}) -- "
                        "the response may be a tool-call-only completion, which this "
                        "provider does not support."
                    )
                return content

            except (requests.exceptions.RequestException, KeyError, IndexError, TypeError) as e:
                # KeyError/IndexError/TypeError: a 200 response whose body
                # doesn't have the expected {"choices": [{"message": {...}}]}
                # shape (e.g. an error payload, or "choices": []) -- without
                # this, such a response bypassed the retry loop entirely and
                # crashed with a bare, unhandled exception instead of the
                # same friendly, retried failure path a network error gets.
                print(f"[GROQ API ERROR] attempt {attempt}: {str(e)}")
                if attempt == _MAX_RETRIES:
                    if isinstance(e, requests.exceptions.RequestException) and "429" in str(e):
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
