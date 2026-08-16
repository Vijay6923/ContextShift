"""
Tests for `python -m contextshift.benchmark` -- the CLI entry point
that makes every benchmark claim in README.md and docs/decisions/
reproducible with one command. Calls contextshift.benchmark.__main__.main()
directly (with an explicit argv list) rather than shelling out to a
subprocess, the same way argparse-based CLIs are conventionally tested.
"""
import pytest

from contextshift.benchmark.__main__ import main


def test_default_suite_is_standard(capsys):
    exit_code = main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("| Strategy |")
    assert "RecencyStrategy" in out
    assert "SlidingWindowStrategy" in out
    assert "PinnedRecencyStrategy" in out
    # The 'standard' suite runs run_benchmark(), not run_needle_benchmark()
    # -- no needle-retention columns.
    assert "Needle Retention" not in out


def test_needle_suite_matches_the_published_readme_table(capsys):
    exit_code = main(["--suite", "needle"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Needle Retention" in out
    assert "Probes Satisfied" in out
    # Exact numbers from docs/benchmarks/needle.md and README.md's
    # needle-retention table -- this test is the thing that would fail
    # first if the fixture suite or a strategy's behavior ever drifted
    # from what's published.
    assert "22 / 55 (40.00%)" in out  # PinnedRecencyStrategy
    assert "14 / 55 (25.45%)" in out  # RecencyStrategy
    assert "7 / 55 (12.73%)" in out  # SlidingWindowStrategy


def test_tokenizer_suite_matches_the_published_adr_table(capsys):
    exit_code = main(["--suite", "tokenizer"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "HeuristicTokenizer" in out
    assert "TiktokenTokenizer" in out
    # Exact numbers from docs/decisions/0014-accurate-tokenizers.md.
    assert "9.60" in out
    assert "27.77%" in out
    assert "93.33%" in out


def test_max_tokens_and_safety_margin_are_overridable(capsys):
    main(["--suite", "needle", "--max-tokens", "100000", "--safety-margin", "0"])
    generous = capsys.readouterr().out

    main(["--suite", "needle"])  # defaults: 350 / 50
    tight = capsys.readouterr().out

    # A budget generous enough to fit the whole fixture suite must push
    # RecencyStrategy (no fixed window) to full needle retention -- not
    # just "different output," but different in the expected direction.
    assert "RecencyStrategy | 2232 | 0 | 39148 | 0 | 100.00%" in generous
    assert generous != tight


def test_unknown_suite_is_rejected():
    with pytest.raises(SystemExit):
        main(["--suite", "nonexistent"])


def test_help_does_not_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
