"""
Authoring tool for the needle-retention fixture suite -- not a fixture
itself, not imported by the benchmark or the test suite.

Run directly to (re)generate every fixture JSON file in this directory:

    python tests/fixtures/conversations/_generate.py

Fixture content is written here, by hand, once -- before any strategy
is ever run against it, per the fixture-honesty note in
docs/decisions/0013-needle-retention-benchmark.md. Token counts are
computed with the real HeuristicTokenizer so fixtures are internally
consistent with what the running application would actually compute,
not arbitrary round numbers.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from contextshift.tokenizers import HeuristicTokenizer

OUT_DIR = Path(__file__).resolve().parent
_tokenizer = HeuristicTokenizer()


def msg(role, content, pinned=False):
    return {
        "role": role,
        "content": content,
        "token_count": _tokenizer.estimate_tokens(content),
        "is_pinned": pinned,
    }


def probe(question, indices, expected_answer=None):
    d = {"question": question, "load_bearing_indices": list(indices)}
    if expected_answer is not None:
        d["expected_answer"] = expected_answer
    return d


def filler_exchange(topic, i):
    return [
        msg("user", f"Can you help me with a {topic} issue, number {i}? It's about the {topic} module."),
        msg(
            "assistant",
            f"Sure -- for {topic} issue {i}, check the config and confirm the module is imported correctly.",
        ),
    ]


def write(name, failure_mode, description, messages, probes):
    data = {
        "name": name,
        "failure_mode": failure_mode,
        "description": description,
        "messages": messages,
        "probes": probes,
    }
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(messages)} messages, {len(probes)} probes)")


# --- 1. early-establishment ---------------------------------------------

def build_early_establishment():
    messages = [
        msg("user", "My name is Priya and I'm building a recipe-recommendation app in Python."),
        msg("assistant", "Got it, Priya -- happy to help with your recipe-recommendation app."),
    ]
    for i in range(18):
        messages += filler_exchange("dependency", i)
    messages.append(msg("user", "Quick recap -- what's my name, and what app am I building?"))

    probes = [
        probe(
            "What is the user's name and what app are they building?",
            [0],
            "Priya, a recipe-recommendation app",
        )
    ]
    write(
        "early-establishment",
        "early-establishment",
        "A fact (name + project) is set in the first message and referenced 38 turns later, "
        "with nothing but unrelated filler in between.",
        messages,
        probes,
    )


# --- 2. early-establishment-numeric (second variant) ---------------------

def build_early_establishment_numeric():
    messages = [
        msg("user", "Our team's budget for this quarter is exactly $42,000."),
        msg("assistant", "Noted -- $42,000 for the quarter."),
    ]
    for i in range(20):
        messages += filler_exchange("scheduling", i)
    messages.append(msg("user", "Reminder -- what was the quarterly budget number again?"))

    probes = [probe("What is the team's quarterly budget?", [0], "$42,000")]
    write(
        "early-establishment-numeric",
        "early-establishment",
        "A numeric fact set once at the very start of a long conversation, referenced only "
        "at the very end -- the same failure mode as early-establishment, with a number "
        "instead of a name to check strategies don't treat the two differently.",
        messages,
        probes,
    )


# --- 3. topic-drift --------------------------------------------------------

def build_topic_drift():
    messages = [
        msg("user", "I'm choosing between PostgreSQL and MongoDB for a new project. I'll pick PostgreSQL."),
        msg("assistant", "PostgreSQL is a solid choice for relational data with strong consistency needs."),
    ]
    for topic in ["frontend framework", "CI pipeline", "logging setup", "deployment target", "auth provider"]:
        for i in range(4):
            messages += filler_exchange(topic, i)
    messages.append(msg("user", "Going back to the very start -- which database did I decide on?"))

    probes = [probe("Which database did the user decide to use?", [0], "PostgreSQL")]
    write(
        "topic-drift",
        "topic-drift",
        "The conversation drifts through five unrelated topics after an early decision is "
        "made, then circles back to ask about that original decision.",
        messages,
        probes,
    )


# --- 4. interleaved-threads ------------------------------------------------

def build_interleaved_threads():
    messages = []
    for i in range(15):
        messages.append(msg("user", f"[Project Atlas] status update {i}: still investigating the timeout bug."))
        messages.append(msg("assistant", f"[Project Atlas] Noted, update {i} logged."))
        messages.append(msg("user", f"[Project Nova] status update {i}: on track, no blockers."))
        messages.append(msg("assistant", f"[Project Nova] Noted, update {i} logged."))
    messages.append(
        msg(
            "user",
            "[Project Atlas] One more thing -- the timeout bug turns out to be caused by a "
            "misconfigured connection pool size of 5, should be 50.",
        )
    )
    messages.append(msg("assistant", "[Project Atlas] Got it -- connection pool size 5 should be 50."))
    messages.append(msg("user", "What was the root cause of the Project Atlas timeout bug?"))

    root_cause_index = len(messages) - 3  # the "misconfigured connection pool" message
    probes = [
        probe(
            "What was the root cause of the Project Atlas timeout bug?",
            [root_cause_index],
            "misconfigured connection pool size (5 instead of 50)",
        )
    ]
    write(
        "interleaved-threads",
        "interleaved-threads",
        "Two unrelated project threads (Atlas, Nova) are interleaved turn by turn for 60 "
        "messages; the answer to the final question depends on one specific message from "
        "only one of the two threads, near the end.",
        messages,
        probes,
    )


# --- 5. correction-of-earlier-answer ---------------------------------------

def build_correction():
    messages = [
        msg("user", "My flight departs at 3pm on Friday."),
        msg("assistant", "Got it -- Friday, 3pm departure."),
    ]
    for i in range(10):
        messages += filler_exchange("itinerary", i)
    messages.append(
        msg(
            "user",
            "Actually, I made a mistake earlier -- my flight departs at 6pm on Friday, not 3pm. "
            "Please use 6pm going forward.",
        )
    )
    messages.append(msg("assistant", "Understood -- updated to 6pm on Friday."))
    for i in range(10, 16):
        messages += filler_exchange("itinerary", i)
    messages.append(msg("user", "What time does my flight actually depart?"))

    # The correction message comes right after the 2 setup messages and 10
    # filler exchanges (2 messages each) that precede it.
    correction_index = 2 + 10 * 2
    probes = [
        probe(
            "What time does the user's flight actually depart?",
            [correction_index],
            "6pm on Friday",
        )
    ]
    write(
        "correction-of-earlier-answer",
        "correction-of-earlier-answer",
        "The user states a fact, then explicitly corrects it partway through a long "
        "conversation. Answering correctly depends only on the correction message surviving "
        "-- not the original, now-wrong statement.",
        messages,
        probes,
    )


# --- 6. long-tool-output -----------------------------------------------

def build_long_tool_output():
    log_lines = [f"[INFO] worker-{i:03d} processed batch {i} in {100 + i}ms" for i in range(80)]
    log_lines.insert(
        41, "[ERROR] worker-041 crashed: OutOfMemoryError while loading model checkpoint 'v3-large.bin'"
    )
    tool_output = "\n".join(log_lines)

    messages = [
        msg("user", "Here's the full log from last night's batch run, can you find what went wrong?"),
        msg("assistant", tool_output),
    ]
    for i in range(15):
        messages += filler_exchange("infrastructure", i)
    messages.append(msg("user", "Which worker crashed, and why?"))

    probes = [
        probe(
            "Which worker crashed in the batch run, and why?",
            [1],
            "worker-041 crashed with an OutOfMemoryError loading the model checkpoint",
        )
    ]
    write(
        "long-tool-output",
        "long-tool-output",
        "A single very large tool-output message (an 80-line log dump) contains one buried "
        "error line that answers the eventual question. Tests whether a strategy's pruning "
        "treats one expensive message fairly or drops it wholesale because of its size.",
        messages,
        probes,
    )


# --- 7. pinned-instruction-under-pressure -----------------------------------

def build_pinned_under_pressure():
    messages = [
        msg("system", "Always respond in formal English and never use contractions.", pinned=True),
    ]
    for i in range(30):
        messages += filler_exchange("formatting", i)
    messages.append(msg("user", "What are your instructions for how to respond?"))

    probes = [
        probe(
            "What instruction was the assistant given for how to respond?",
            [0],
            "Always respond in formal English and never use contractions",
        )
    ]
    write(
        "pinned-instruction-under-pressure",
        "pinned-instruction-under-pressure",
        "A pinned system instruction sits at the start of a long, high-token conversation "
        "that would force it out under a tight budget if it weren't pinned. The strategies "
        "that don't support pinning are expected to lose it; that's the point of this fixture.",
        messages,
        probes,
    )


# --- 8. topic-drift-gradual (second drift variant) --------------------------

def build_topic_drift_gradual():
    messages = [
        msg("user", "The API rate limit we agreed on is 100 requests per minute."),
        msg("assistant", "100 requests per minute, understood."),
    ]
    topics = ["pagination", "pagination", "caching", "caching", "caching", "retries", "retries", "webhooks"]
    for idx, topic in enumerate(topics):
        messages += filler_exchange(topic, idx)
    messages.append(msg("user", "Before I forget -- what rate limit did we agree on?"))

    probes = [probe("What API rate limit was agreed on?", [0], "100 requests per minute")]
    write(
        "topic-drift-gradual",
        "topic-drift",
        "Similar to topic-drift, but the drift is gradual (each topic overlaps with the "
        "next for a couple of turns) rather than a hard switch -- checks that strategies "
        "aren't accidentally relying on abrupt topic boundaries.",
        messages,
        probes,
    )


# --- 9. interleaved-threads-triple (three threads) --------------------------

def build_interleaved_triple():
    messages = []
    for i in range(10):
        for project in ["Atlas", "Nova", "Comet"]:
            messages.append(msg("user", f"[{project}] update {i}: nothing new to report."))
            messages.append(msg("assistant", f"[{project}] Noted."))
    messages.append(msg("user", "[Comet] Correction -- Comet's launch date is now March 3rd, not March 1st."))
    messages.append(msg("assistant", "[Comet] Updated -- launch date is March 3rd."))
    messages.append(msg("user", "What is Comet's launch date?"))

    launch_index = len(messages) - 3
    probes = [probe("What is Project Comet's launch date?", [launch_index], "March 3rd")]
    write(
        "interleaved-threads-triple",
        "interleaved-threads",
        "Three interleaved project threads instead of two, raising the ratio of irrelevant "
        "to relevant messages the strategy has to sort through before the final question.",
        messages,
        probes,
    )


# --- 10. multi-probe-mixed (stress test, several failure modes at once) ----

def build_multi_probe_mixed():
    messages = [
        msg("system", "Always include units when stating a measurement.", pinned=True),
        msg("user", "The server's max memory is 16GB."),
        msg("assistant", "16GB max memory, noted."),
    ]
    for i in range(12):
        messages += filler_exchange("monitoring", i)
    messages.append(msg("user", "Correction -- the max memory is actually 32GB, we upgraded last week."))
    messages.append(msg("assistant", "Updated -- 32GB max memory."))
    for i in range(12, 20):
        messages += filler_exchange("monitoring", i)
    messages.append(msg("user", "What's our current server memory limit, and what's your formatting instruction?"))

    memory_correction_index = 3 + 12 * 2  # after pinned + setup(2) + 12 filler exchanges
    probes = [
        probe("What is the server's current max memory?", [memory_correction_index], "32GB"),
        probe("What formatting instruction was given?", [0], "always include units when stating a measurement"),
    ]
    write(
        "multi-probe-mixed",
        "correction-of-earlier-answer",
        "Combines a pinned instruction with a mid-conversation correction and heavy filler, "
        "checked by two independent probes -- a stress test mixing several failure modes "
        "the single-mode fixtures isolate individually.",
        messages,
        probes,
    )


if __name__ == "__main__":
    build_early_establishment()
    build_early_establishment_numeric()
    build_topic_drift()
    build_interleaved_threads()
    build_correction()
    build_long_tool_output()
    build_pinned_under_pressure()
    build_topic_drift_gradual()
    build_interleaved_triple()
    build_multi_probe_mixed()
