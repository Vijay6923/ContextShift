"""
Application-side translation between SQLAlchemy ORM Message rows and
contextshift.core.Message, plus factory helpers that construct
correctly-configured contextshift objects from this application's
Config.

Deliberately NOT part of contextshift/ -- an adapter's entire job is to
know about both sides of the Application/Library boundary (ORM rows and
Config on one side; core.Message and library objects on the other), and
code that knows about both sides cannot live on the side that's supposed
to know about neither. See
docs/decisions/0001-library-independence-and-adapter-placement.md.

app.py imports this module itself (`import adapters`), not individual
names from it (never `from adapters import build_provider`), and this
module imports contextshift subpackages the same way. That means a test
can monkeypatch a single factory function (e.g. `adapters.build_provider`)
and have every caller see the patched version, with no real network
access required to test any route that depends on an LLM call.
"""
from __future__ import annotations

from config import Config
from contextshift import ContextManager
from contextshift.core import Message as CoreMessage
from contextshift.core import TokenBudget
from contextshift.llm import OpenRouterProvider
from contextshift.strategies import PinnedRecencyStrategy, total_tokens
from contextshift.summarization import Summarizer
from contextshift.tokenizers import HeuristicTokenizer
from contextshift.vision import GeminiVisionProvider

_CHAT_SYSTEM_PROMPT = (
    "You are a helpful assistant. The conversation history below may "
    "include a summary of earlier messages."
)


def to_core_message(orm_message) -> CoreMessage:
    """Translate one SQLAlchemy Message row into a library-neutral core.Message."""
    return CoreMessage(
        role=orm_message.role,
        content=orm_message.content,
        is_pinned=orm_message.is_pinned,
        token_count=orm_message.token_count,
    )


def to_core_messages(orm_messages) -> list[CoreMessage]:
    """Translate a list of SQLAlchemy Message rows into core.Message objects, preserving order."""
    return [to_core_message(m) for m in orm_messages]


def build_budget() -> TokenBudget:
    return TokenBudget(max_tokens=Config.MAX_TOKENS, safety_margin=Config.TOKEN_SAFETY_MARGIN)


def build_strategy() -> PinnedRecencyStrategy:
    return PinnedRecencyStrategy(recent_buffer=Config.RECENT_BUFFER)


def build_tokenizer() -> HeuristicTokenizer:
    return HeuristicTokenizer()


def build_provider() -> OpenRouterProvider:
    """
    Construct an OpenRouterProvider from application config.

    Deliberately called fresh at each use site within a route, never
    constructed once at module import time. OpenRouterProvider validates
    `api_key` at construction (ADR 0006); constructing it eagerly at
    import time would mean the app refuses to boot at all if
    `OPENROUTER_API_KEY` is unset. Calling this lazily, from inside each
    route that needs it, means the app boots fine either way and only the
    specific routes that need OpenRouter fail if the key is missing.
    """
    return OpenRouterProvider(
        api_key=Config.OPENROUTER_API_KEY,
        model=Config.OPENROUTER_MODEL,
        base_url=Config.OPENROUTER_BASE_URL,
    )


def build_vision_provider() -> GeminiVisionProvider:
    """
    Construct a GeminiVisionProvider from application config.

    Deliberately called fresh at each use site, never constructed once
    at module import time -- for the same reason as build_provider():
    GeminiVisionProvider validates `api_key` at construction, so the app
    must still boot even if GEMINI_API_KEY is unset.
    """
    return GeminiVisionProvider(api_key=Config.GEMINI_API_KEY, model=Config.GEMINI_MODEL)


def build_summarizer() -> Summarizer:
    return Summarizer(build_provider())


def build_context_manager() -> ContextManager:
    """
    Construct a ContextManager from application config.

    Deliberately called fresh at each use site, never constructed once
    at module import time -- for the same reason as build_provider(),
    which it wraps: OpenRouterProvider validates `api_key` at
    construction, so building this eagerly at import time would mean the
    app refuses to boot at all if `OPENROUTER_API_KEY` is unset.

    `system_prompt` is the application's own text, not the library's
    (ADR 0004, ADR 0006, ADR 0011 Non-goals): this is the one place in
    the application that owns the exact system prompt sent to the model.
    """
    return ContextManager(
        strategy=build_strategy(),
        provider=build_provider(),
        tokenizer=build_tokenizer(),
        budget=build_budget(),
        system_prompt=_CHAT_SYSTEM_PROMPT,
    )


def compute_token_stats(orm_messages) -> dict:
    """
    Reproduce the {current_tokens, max_tokens, percentage} shape the
    Flask app's routes return to the frontend's token-usage progress bar.

    This is application-facing presentation output (JSON for one
    specific UI), not a library concern -- see ADR 0003 for why this
    stays application-side rather than becoming part of contextshift's
    public surface.
    """
    core_messages = to_core_messages(orm_messages)
    budget = build_budget()
    current = total_tokens(core_messages)
    percentage = round((current / budget.max_tokens) * 100, 2)
    return {
        "current_tokens": current,
        "max_tokens": budget.max_tokens,
        "percentage": percentage,
    }
