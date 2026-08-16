# Lessons

Short, dated notes on mistakes worth not repeating — not a full postmortem
process, just enough to keep from relearning the same thing twice.

## A `mypy --strict` fix is a runtime change until proven otherwise

**What happened:** Bringing `contextshift/` under `mypy --strict` for CI
surfaced several real type errors. Two of the fixes, applied to satisfy
the type checker, silently introduced real runtime bugs:

- `contextshift/llm/groq.py` — `complete()` is declared `-> str`, but
  `response.json()["choices"][0]["message"]["content"]` is typed `Any`.
  The fix was `return str(response.json()[...])`. That satisfies mypy —
  and also means a real `content: null` response (a legitimate Groq
  response shape, e.g. a tool-call-only completion) silently becomes
  the three-character string `"None"` instead of failing loudly. mypy
  has no opinion on this: `str(None)` is a perfectly well-typed
  expression.
- `contextshift/ingestion/image.py` — `Image.LANCZOS` (works on every
  Pillow version this project has ever declared support for) was
  changed to `Image.Resampling.LANCZOS` to satisfy a stub-typing
  complaint. `Image.Resampling` was added in Pillow 9.1 —
  `pyproject.toml` still declared `Pillow>=9.0`. The type checker had
  no way to know the runtime dependency floor didn't match what the
  new code actually required.

Both fixes were verified by `mypy --strict` passing and the existing
test suite staying green — and both were still real, live bugs,
because neither existing test exercised the specific runtime path that
broke (a null-content response; an environment on the declared minimum
Pillow version). The type checker and the test suite were each
individually clean; the two facts they were each individually
confirming didn't overlap.

## The rule

**A `mypy --strict` fix that changes what the code actually *does* at
runtime — a `cast`/`str()`/`int()` wrap, a version-specific API call, a
broadened or narrowed `except` clause, an added `isinstance` branch —
is a behavior change, not a type annotation, and gets flagged and
tested as one.** Concretely:

1. **Say so in the diff.** A one-line comment at the change site (or in
   the commit message) naming *what runtime assumption this fix now
   makes* — "requires Pillow>=9.1", "assumes `content` is never null" —
   turns an invisible assumption into a reviewable one.
2. **Pair it with a regression test that exercises the runtime path,
   not the type.** `mypy --strict` passing proves the code type-checks
   under the assumption; it says nothing about whether the assumption
   holds at runtime, or about what happens when it doesn't. A test
   that simulates the actual broken input (a null-content API
   response; a Pillow build without `Image.Resampling`, via
   `monkeypatch`) is what would have caught both bugs above before
   they shipped — see `tests/test_llm_characterization.py::test_complete_raises_on_null_content_instead_of_returning_the_string_none`
   and `tests/test_ingestion_image.py::test_falls_back_gracefully_if_pillow_lacks_the_resampling_enum`
   for the tests that now do this.
3. **Don't let a clean `mypy --strict` run stand in for a clean runtime
   check.** They answer different questions. Passing both is the bar;
   passing only one and assuming the other follows is exactly the gap
   both bugs above lived in.
