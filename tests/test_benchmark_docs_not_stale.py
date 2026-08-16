"""
Regression test: the committed tables in docs/benchmarks/ must match
what `python -m contextshift.benchmark` actually produces right now.

docs/benchmarks/*.md wrap the raw CLI output in explanatory prose (see
docs/benchmarks/README.md), so this doesn't diff the files byte-for-byte
-- it extracts each file's Markdown table (the `| ... |` lines),
strips the "Latency (s)" column (wall-clock, expected to vary run to
run and machine to machine -- not a claim this project makes), and
compares what's left exactly against a fresh run. A strategy change, a
fixture change, or a tokenizer change that shifts these numbers should
fail here, not go unnoticed until someone reads the docs and the code
disagreeing by hand.
"""
from pathlib import Path

from contextshift.benchmark.__main__ import (
    _run_needle,
    _run_standard,
    _run_tokenizer,
)

DOCS_DIR = Path(__file__).parent.parent / "docs" / "benchmarks"


def _stable_rows(text: str) -> list[list[str]]:
    """Parse a Markdown table's `| ... |` lines into cells, dropping the Latency (s) column if present."""
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("|")
    ]
    header = rows[0]
    if "Latency (s)" not in header:
        return rows
    latency_index = header.index("Latency (s)")
    return [[cell for i, cell in enumerate(row) if i != latency_index] for row in rows]


def test_standard_md_matches_a_fresh_run():
    committed = _stable_rows((DOCS_DIR / "standard.md").read_text())
    fresh = _stable_rows(_run_standard(None, None))
    assert committed == fresh


def test_needle_md_matches_a_fresh_run():
    committed = _stable_rows((DOCS_DIR / "needle.md").read_text())
    fresh = _stable_rows(_run_needle(None, None))
    assert committed == fresh


def test_tokenizer_md_matches_a_fresh_run():
    committed = _stable_rows((DOCS_DIR / "tokenizer.md").read_text())
    fresh = _stable_rows(_run_tokenizer())
    assert committed == fresh
