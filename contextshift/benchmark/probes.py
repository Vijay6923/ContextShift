"""
Probes and conversation fixtures for the needle-retention benchmark.

A strategy's own metrics (messages kept, tokens kept) are tautological
by construction: a strategy that is *defined* as "keep the last N
messages" will, of course, report that it kept N messages. That's not
a measurement of anything -- it's restating the strategy's definition.

The question worth asking is different: when a strategy drops
messages, does it drop the ones a later question actually depends on?
That's answerable without a model call, as long as which messages are
"load-bearing" for a given question is decided once, by a human,
ahead of time -- not inferred at benchmark time. That's what a Probe
records.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contextshift.core import Message


@dataclass(frozen=True, slots=True)
class Probe:
    """
    One checkable question about a conversation, and which messages
    answering it actually depends on.

    Args:
        question: The question this probe represents. Not sent to any
            model by the deterministic tier (see `needle.py`) --
            present for readability and reused by the opt-in
            LLM-scored tier.
        load_bearing_indices: Positions into the owning fixture's
            `messages` tuple -- every message required to answer
            `question` correctly. A probe counts as satisfied only if
            *all* of them survive a strategy's selection; losing even
            one is treated as a failure to answer, the same way a
            person missing one fact usually can't give a complete
            answer either.
        expected_answer: Optional. Only used by the opt-in LLM-scored
            tier (`judge.py`), which asks a real model the question and
            checks its answer against this. The deterministic tier
            never reads this field.
    """

    question: str
    load_bearing_indices: tuple[int, ...]
    expected_answer: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationFixture:
    """
    A hand-authored conversation, plus the probes that make it useful
    for measuring what a strategy actually preserves -- not just
    running one against it.

    Args:
        name: Short, stable identifier. Matches the JSON filename
            (without extension) fixtures are loaded from.
        failure_mode: Which specific way of losing information this
            fixture is designed to expose (e.g. "early-establishment",
            "topic-drift") -- see
            tests/fixtures/conversations/README.md for the full list
            and what each one means.
        description: One or two sentences of human context: what
            happens in this conversation and why it's a meaningful
            test, beyond the failure-mode label alone.
        messages: The conversation, in original order. Never mutated
            by anything in this package.
        probes: What matters in this conversation, and exactly where.
    """

    name: str
    failure_mode: str
    description: str
    messages: tuple[Message, ...]
    probes: tuple[Probe, ...]


def load_fixture(path: Path) -> ConversationFixture:
    """Load one conversation fixture from a JSON file. Raises on malformed input rather than guessing."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    messages = tuple(
        Message(
            role=m["role"],
            content=m["content"],
            token_count=m["token_count"],
            is_pinned=m.get("is_pinned", False),
        )
        for m in data["messages"]
    )
    probes = tuple(
        Probe(
            question=p["question"],
            load_bearing_indices=tuple(p["load_bearing_indices"]),
            expected_answer=p.get("expected_answer"),
        )
        for p in data["probes"]
    )

    for probe in probes:
        for idx in probe.load_bearing_indices:
            if not (0 <= idx < len(messages)):
                raise ValueError(
                    f"{path}: probe {probe.question!r} references message index {idx}, "
                    f"but this fixture only has {len(messages)} messages."
                )

    return ConversationFixture(
        name=data["name"],
        failure_mode=data["failure_mode"],
        description=data["description"],
        messages=messages,
        probes=probes,
    )


def load_fixtures(directory: Path) -> list[ConversationFixture]:
    """
    Load every `*.json` fixture in `directory`, sorted by filename for
    deterministic ordering. Returns an empty list for an empty or
    missing directory -- callers that require at least one fixture
    should check the result themselves.
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    return [load_fixture(p) for p in sorted(directory.glob("*.json"))]


def fixture_to_dict(fixture: ConversationFixture) -> dict[str, Any]:
    """The inverse of `load_fixture` -- used by the fixture-authoring script, not by the benchmark itself."""
    return {
        "name": fixture.name,
        "failure_mode": fixture.failure_mode,
        "description": fixture.description,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "token_count": m.token_count,
                "is_pinned": m.is_pinned,
            }
            for m in fixture.messages
        ],
        "probes": [
            {
                "question": p.question,
                "load_bearing_indices": list(p.load_bearing_indices),
                **({"expected_answer": p.expected_answer} if p.expected_answer is not None else {}),
            }
            for p in fixture.probes
        ],
    }
