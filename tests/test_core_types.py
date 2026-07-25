"""
Tests for contextshift.core's foundation types. Pure, DB-free, no Flask
involved -- these are meant to be usable by the CLI, the eval harness, and
external consumers just as much as by the Flask app, so they're verified
the same way.
"""
import dataclasses

import pytest

from contextshift.core import Message, TokenBudget


def test_message_requires_only_role_and_content():
    msg = Message(role="user", content="hello")

    assert msg.role == "user"
    assert msg.content == "hello"
    assert msg.is_pinned is False
    assert msg.token_count is None


def test_message_token_count_none_is_distinct_from_zero():
    unmeasured = Message(role="user", content="hello")
    measured_as_zero = Message(role="user", content="", token_count=0)

    assert unmeasured.token_count is None
    assert measured_as_zero.token_count == 0
    assert unmeasured != measured_as_zero


def test_message_is_immutable():
    msg = Message(role="user", content="hello")

    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.content = "changed"


def test_message_equality_is_value_based():
    a = Message(role="user", content="hi", token_count=5)
    b = Message(role="user", content="hi", token_count=5)
    c = Message(role="user", content="hi", token_count=6)

    assert a == b
    assert a != c


def test_token_budget_effective_limit_subtracts_safety_margin():
    budget = TokenBudget(max_tokens=4000, safety_margin=200)
    assert budget.effective_limit == 3800


def test_token_budget_safety_margin_defaults_to_zero():
    budget = TokenBudget(max_tokens=1000)
    assert budget.safety_margin == 0
    assert budget.effective_limit == 1000


def test_token_budget_is_immutable():
    budget = TokenBudget(max_tokens=1000)

    with pytest.raises(dataclasses.FrozenInstanceError):
        budget.max_tokens = 2000


@pytest.mark.parametrize(
    "max_tokens, safety_margin",
    [
        (0, 0),  # max_tokens must be positive
        (-100, 0),  # max_tokens must be positive
        (1000, -1),  # safety_margin must be non-negative
        (1000, 1001),  # safety_margin cannot exceed max_tokens
    ],
)
def test_token_budget_rejects_invalid_values(max_tokens, safety_margin):
    with pytest.raises(ValueError):
        TokenBudget(max_tokens=max_tokens, safety_margin=safety_margin)
