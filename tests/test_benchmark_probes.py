"""Tests for contextshift.benchmark.probes: Probe, ConversationFixture, and JSON loading."""
import json

import pytest

from contextshift.benchmark.probes import (
    ConversationFixture,
    Probe,
    fixture_to_dict,
    load_fixture,
    load_fixtures,
)
from contextshift.core import Message


def _write_fixture(tmp_path, name, messages, probes):
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "failure_mode": "test-mode",
                "description": "A test fixture.",
                "messages": messages,
                "probes": probes,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_fixture_round_trips_messages_and_probes(tmp_path):
    path = _write_fixture(
        tmp_path,
        "sample",
        messages=[
            {"role": "user", "content": "hello", "token_count": 5, "is_pinned": False},
            {"role": "assistant", "content": "hi", "token_count": 3},
        ],
        probes=[{"question": "What did the user say?", "load_bearing_indices": [0], "expected_answer": "hello"}],
    )

    fixture = load_fixture(path)

    assert fixture.name == "sample"
    assert fixture.failure_mode == "test-mode"
    assert len(fixture.messages) == 2
    assert fixture.messages[0] == Message(role="user", content="hello", token_count=5, is_pinned=False)
    assert fixture.messages[1].is_pinned is False  # default applied when omitted
    assert len(fixture.probes) == 1
    assert fixture.probes[0].load_bearing_indices == (0,)
    assert fixture.probes[0].expected_answer == "hello"


def test_load_fixture_probe_without_expected_answer(tmp_path):
    path = _write_fixture(
        tmp_path,
        "no-answer",
        messages=[{"role": "user", "content": "hi", "token_count": 3}],
        probes=[{"question": "q", "load_bearing_indices": [0]}],
    )

    fixture = load_fixture(path)
    assert fixture.probes[0].expected_answer is None


def test_load_fixture_rejects_out_of_range_index(tmp_path):
    path = _write_fixture(
        tmp_path,
        "bad",
        messages=[{"role": "user", "content": "hi", "token_count": 3}],
        probes=[{"question": "q", "load_bearing_indices": [5]}],
    )

    with pytest.raises(ValueError, match="message index 5"):
        load_fixture(path)


def test_load_fixtures_loads_every_json_file_sorted(tmp_path):
    _write_fixture(tmp_path, "zebra", [{"role": "user", "content": "a", "token_count": 1}], [])
    _write_fixture(tmp_path, "alpha", [{"role": "user", "content": "b", "token_count": 1}], [])

    fixtures = load_fixtures(tmp_path)

    assert [f.name for f in fixtures] == ["alpha", "zebra"]


def test_load_fixtures_of_missing_directory_returns_empty_list(tmp_path):
    assert load_fixtures(tmp_path / "does-not-exist") == []


def test_fixture_to_dict_is_the_inverse_of_load_fixture(tmp_path):
    path = _write_fixture(
        tmp_path,
        "roundtrip",
        messages=[{"role": "user", "content": "hi", "token_count": 3, "is_pinned": True}],
        probes=[{"question": "q", "load_bearing_indices": [0], "expected_answer": "a"}],
    )
    fixture = load_fixture(path)

    as_dict = fixture_to_dict(fixture)
    reloaded_path = tmp_path / "reloaded.json"
    reloaded_path.write_text(json.dumps(as_dict), encoding="utf-8")
    reloaded = load_fixture(reloaded_path)

    assert reloaded.messages == fixture.messages
    assert reloaded.probes == fixture.probes


def test_probe_and_fixture_are_frozen():
    import dataclasses

    probe = Probe(question="q", load_bearing_indices=(0,))
    with pytest.raises(dataclasses.FrozenInstanceError):
        probe.question = "changed"

    fixture = ConversationFixture(name="x", failure_mode="y", description="z", messages=(), probes=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        fixture.name = "changed"
