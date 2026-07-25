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
and have every caller see the patched version -- the exact pattern the
pre-migration test suite already relied on for `utils.summarizer`.
"""
from __future__ import annotations

from config import Config
from contextshift.core import Message as CoreMessage
from contextshift.core import TokenBudget
from contextshift.llm import GroqProvider
from contextshift.strategies import PinnedRecencyStrategy, total_tokens
from contextshift.summarization import Summarizer
from contextshift.tokenizers import HeuristicTokenizer

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


def build_provider() -> GroqProvider:
    """
    Construct a GroqProvider from application config.

    Deliberately called fresh at each use site within a route, never
    constructed once at module import time -- GroqProvider validates
    api_key at construction (Step 5 / ADR 0006), and legacy's equivalent
    check (`if not Config.GROQ_API_KEY: raise ValueError`) only ever ran
    when a route actually needed to call Groq, not at application
    startup. Constructing eagerly at import time would change that
    failure mode: the app would refuse to boot at all if GROQ_API_KEY
    were unset, instead of booting fine and only failing the specific
    routes that need it, exactly as legacy behaves.
    """
    return GroqProvider(api_key=Config.GROQ_API_KEY, model=Config.GROQ_MODEL, base_url=Config.GROQ_BASE_URL)


def build_summarizer() -> Summarizer:
    return Summarizer(build_provider())


def build_chat_context(orm_messages) -> list[CoreMessage]:
    """
    Select context via the pinned/recency strategy and prepend the
    application's system prompt.

    Legacy's context_builder.build_context() combined message selection
    and system-prompt framing into one function. ADR 0004 and ADR 0006
    deliberately kept prompt construction out of contextshift/, leaving
    it for whatever orchestrates a strategy result into a provider call
    to decide. This function is that orchestration -- the one place in
    the application that owns the exact system prompt text.
    """
    core_messages = to_core_messages(orm_messages)
    result = build_strategy().build(core_messages, build_budget())
    system_message = CoreMessage(role="system", content=_CHAT_SYSTEM_PROMPT)
    return [system_message] + result.messages


def compute_token_stats(orm_messages) -> dict:
    """
    Reproduce the {current_tokens, max_tokens, percentage} shape the
    Flask app's routes return to the frontend's token-usage progress bar.

    This is application-facing presentation output (JSON for one
    specific UI), not a library concern -- ADR 0003 identified this as a
    strong candidate for staying application-side rather than becoming
    part of contextshift's public surface. This is that decision acted
    on.
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
