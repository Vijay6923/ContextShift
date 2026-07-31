"""Tests for the ContextStrategy protocol, ContextResult, and the total_tokens helper."""
import dataclasses

import pytest

from contextshift.core import Message
from contextshift.strategies import (
    ContextResult,
    ContextStrategy,
    PinnedRecencyStrategy,
    RecencyStrategy,
    SlidingWindowStrategy,
)
from contextshift.strategies.base import total_tokens


def _msg(role="user", content="x", token_count=10, is_pinned=False):
    return Message(role=role, content=content, token_count=token_count, is_pinned=is_pinned)


def test_context_result_is_immutable():
    result = ContextResult(messages=[_msg()], excluded=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.messages = []


def test_context_result_equality_is_value_based():
    a = ContextResult(messages=[_msg(content="hi")], excluded=[])
    b = ContextResult(messages=[_msg(content="hi")], excluded=[])
    assert a == b


def test_pinned_recency_strategy_satisfies_context_strategy_protocol():
    assert isinstance(PinnedRecencyStrategy(), ContextStrategy)


def test_sliding_window_strategy_satisfies_context_strategy_protocol():
    assert isinstance(SlidingWindowStrategy(), ContextStrategy)


def test_recency_strategy_satisfies_context_strategy_protocol():
    assert isinstance(RecencyStrategy(), ContextStrategy)


def test_something_lacking_build_does_not_satisfy_protocol():
    class NotAStrategy:
        pass

    assert not isinstance(NotAStrategy(), ContextStrategy)


def test_duck_typed_class_satisfies_protocol_structurally():
    class DuckTypedStrategy:
        def build(self, messages, budget):
            return ContextResult(messages=list(messages), excluded=[])

    assert isinstance(DuckTypedStrategy(), ContextStrategy)


def test_total_tokens_sums_measured_messages():
    messages = [_msg(token_count=10), _msg(token_count=25)]
    assert total_tokens(messages) == 35


def test_total_tokens_of_empty_list_is_zero():
    assert total_tokens([]) == 0


def test_total_tokens_raises_on_unmeasured_message():
    messages = [_msg(token_count=10), _msg(token_count=None)]
    with pytest.raises(ValueError, match="token_count"):
        total_tokens(messages)
