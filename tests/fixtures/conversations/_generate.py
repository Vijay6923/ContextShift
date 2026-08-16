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


# =========================================================================
# Expansion (follow-up pass): broadens coverage per failure mode from
# 10 fixtures to 40+, per the same fixture-honesty discipline as the
# original 10 above (docs/decisions/0013-needle-retention-benchmark.md)
# -- every fixture below was written, and its probe indices computed
# mechanically from conversation structure, before any strategy was run
# against the expanded suite. The 10 build_* functions above are
# untouched by this pass; every JSON file they write stays byte-identical.
# =========================================================================

# --- early-establishment: additional variants ---------------------------

_EARLY_ESTABLISHMENT_VARIANTS = [
    dict(
        name="early-establishment-project-id",
        fact_intro="This project's tracking ID is PROJ-88421.",
        fact_ack="Got it -- PROJ-88421.",
        filler_topic="testing",
        filler_count=16,
        question="What was the project tracking ID?",
        expected_answer="PROJ-88421",
    ),
    dict(
        name="early-establishment-address",
        fact_intro="Ship the hardware to 42 Harbor Lane, Unit 7.",
        fact_ack="Noted -- 42 Harbor Lane, Unit 7.",
        filler_topic="logistics",
        filler_count=22,
        question="What shipping address did I give you?",
        expected_answer="42 Harbor Lane, Unit 7",
    ),
    dict(
        name="early-establishment-deadline",
        fact_intro="The submission deadline is November 14th, no extensions.",
        fact_ack="Understood -- November 14th, no extensions.",
        filler_topic="drafting",
        filler_count=17,
        question="When is the submission deadline?",
        expected_answer="November 14th",
    ),
    dict(
        name="early-establishment-api-key-label",
        fact_intro="Label the new API key 'prod-eu-west-1' when you create it.",
        fact_ack="Will do -- labeling it 'prod-eu-west-1'.",
        filler_topic="provisioning",
        filler_count=25,
        question="What label should the new API key have?",
        expected_answer="prod-eu-west-1",
    ),
    dict(
        name="early-establishment-language-preference",
        fact_intro="Please always answer in British English spelling, not American.",
        fact_ack="Understood -- British English spelling throughout.",
        filler_topic="writing",
        filler_count=19,
        question="What spelling convention did I ask you to use?",
        expected_answer="British English",
    ),
    dict(
        name="early-establishment-contact",
        fact_intro="If anything urgent comes up, contact Dev at dev@example.com.",
        fact_ack="Got it -- Dev at dev@example.com for urgent matters.",
        filler_topic="onboarding",
        filler_count=21,
        question="Who should be contacted for urgent matters, and how?",
        expected_answer="Dev at dev@example.com",
    ),
]


def build_early_establishment_variants():
    for v in _EARLY_ESTABLISHMENT_VARIANTS:
        messages = [msg("user", v["fact_intro"]), msg("assistant", v["fact_ack"])]
        for i in range(v["filler_count"]):
            messages += filler_exchange(v["filler_topic"], i)
        messages.append(msg("user", v["question"]))
        probes = [probe(v["question"], [0], v["expected_answer"])]
        write(
            v["name"],
            "early-establishment",
            f"A fact set in the first message, referenced only after {v['filler_count']} "
            "unrelated filler exchanges -- same failure mode as early-establishment, a "
            "different fact/topic combination.",
            messages,
            probes,
        )


# --- topic-drift: additional variants ------------------------------------

_TOPIC_DRIFT_VARIANTS = [
    dict(
        name="topic-drift-cloud-provider",
        decision_statement="I'm choosing AWS over GCP and Azure for this project.",
        decision_ack="AWS it is -- fits your existing tooling well.",
        drift_topics=["networking", "IAM setup", "billing alerts", "region selection"],
        question="Which cloud provider did I decide on?",
        expected_answer="AWS",
    ),
    dict(
        name="topic-drift-language",
        decision_statement="We're writing the new service in Rust, not Go.",
        decision_ack="Rust it is -- good fit for the performance requirements.",
        drift_topics=["build tooling", "linting", "packaging", "editor setup", "CI runners", "release process"],
        question="Which language did we settle on for the new service?",
        expected_answer="Rust",
    ),
    dict(
        name="topic-drift-testing-framework",
        decision_statement="Let's standardize on pytest across all our Python repos.",
        decision_ack="pytest across the board, understood.",
        drift_topics=["fixtures", "mocking", "coverage reporting"],
        question="What testing framework did we standardize on?",
        expected_answer="pytest",
    ),
    dict(
        name="topic-drift-message-queue",
        decision_statement="We'll use Kafka for the event bus instead of RabbitMQ.",
        decision_ack="Kafka for the event bus, noted.",
        drift_topics=["partitioning", "consumer groups", "schema registry", "monitoring", "retention policy"],
        question="Which message queue did we decide to use?",
        expected_answer="Kafka",
    ),
    dict(
        name="topic-drift-api-style",
        decision_statement="The public API will be GraphQL, not REST.",
        decision_ack="GraphQL for the public API, got it.",
        drift_topics=["schema design", "resolvers", "rate limiting", "versioning", "auth", "caching", "docs"],
        question="What style of API did we decide on?",
        expected_answer="GraphQL",
    ),
    dict(
        name="topic-drift-hosting-region",
        decision_statement="We're hosting primarily out of the eu-central-1 region.",
        decision_ack="eu-central-1 as primary region, noted.",
        drift_topics=["latency testing", "failover", "compliance"],
        question="What is our primary hosting region?",
        expected_answer="eu-central-1",
    ),
]


def build_topic_drift_variants():
    for v in _TOPIC_DRIFT_VARIANTS:
        messages = [msg("user", v["decision_statement"]), msg("assistant", v["decision_ack"])]
        for topic in v["drift_topics"]:
            for i in range(4):
                messages += filler_exchange(topic, i)
        messages.append(msg("user", v["question"]))
        probes = [probe(v["question"], [0], v["expected_answer"])]
        write(
            v["name"],
            "topic-drift",
            f"The conversation drifts through {len(v['drift_topics'])} unrelated topics after "
            "an early decision, then circles back to ask about it -- same failure mode as "
            "topic-drift, a different decision/topic combination.",
            messages,
            probes,
        )


# --- interleaved-threads: additional variants (varying thread count) -----

_INTERLEAVED_VARIANTS = [
    dict(
        name="interleaved-threads-two-alt",
        projects=["Falcon", "Orbit"],
        rounds=12,
        correction_project="Orbit",
        correction_text="the release is now gated behind a feature flag called 'orbit-v2'.",
        correction_ack="Updated -- release gated behind feature flag 'orbit-v2'.",
        question="What is Project Orbit's release gated behind?",
        expected_answer="feature flag 'orbit-v2'",
    ),
    dict(
        name="interleaved-threads-quad",
        projects=["Atlas", "Nova", "Comet", "Vega"],
        rounds=8,
        correction_project="Vega",
        correction_text="the budget was revised to $18,500, up from $12,000.",
        correction_ack="Updated -- Vega's budget is now $18,500.",
        question="What is Project Vega's current budget?",
        expected_answer="$18,500",
    ),
    dict(
        name="interleaved-threads-quad-early-correction",
        projects=["Atlas", "Nova", "Comet", "Vega"],
        rounds=8,
        correction_project="Atlas",
        correction_text="the lead engineer changed from Sam to Priya.",
        correction_ack="Updated -- Atlas's lead engineer is now Priya.",
        question="Who is the current lead engineer on Project Atlas?",
        expected_answer="Priya",
        correction_after_round=1,
    ),
    dict(
        name="interleaved-threads-five",
        projects=["Atlas", "Nova", "Comet", "Vega", "Juno"],
        rounds=6,
        correction_project="Juno",
        correction_text="the deployment target moved from staging to production.",
        correction_ack="Updated -- Juno now deploys to production.",
        question="What is Project Juno's current deployment target?",
        expected_answer="production",
    ),
    dict(
        name="interleaved-threads-two-numeric",
        projects=["Falcon", "Orbit"],
        rounds=18,
        correction_project="Falcon",
        correction_text="the error budget was tightened to 0.1%, down from 0.5%.",
        correction_ack="Updated -- Falcon's error budget is now 0.1%.",
        question="What is Project Falcon's current error budget?",
        expected_answer="0.1%",
    ),
    dict(
        name="interleaved-threads-triple-early",
        projects=["Atlas", "Nova", "Comet"],
        rounds=10,
        correction_project="Nova",
        correction_text="the on-call rotation moved from weekly to biweekly.",
        correction_ack="Updated -- Nova's on-call rotation is now biweekly.",
        question="How often does Project Nova's on-call rotation change?",
        expected_answer="biweekly",
        correction_after_round=2,
    ),
]


def build_interleaved_variants():
    for v in _INTERLEAVED_VARIANTS:
        messages = []
        correction_after = v.get("correction_after_round", v["rounds"])
        for i in range(v["rounds"]):
            for project in v["projects"]:
                messages.append(msg("user", f"[{project}] update {i}: nothing new to report."))
                messages.append(msg("assistant", f"[{project}] Noted."))
            if i == correction_after - 1:
                messages.append(msg("user", f"[{v['correction_project']}] Correction -- {v['correction_text']}"))
                messages.append(msg("assistant", f"[{v['correction_project']}] {v['correction_ack']}"))
        messages.append(msg("user", v["question"]))

        correction_index = next(
            i
            for i, m in enumerate(messages)
            if m["content"] == f"[{v['correction_project']}] Correction -- {v['correction_text']}"
        )
        probes = [probe(v["question"], [correction_index], v["expected_answer"])]
        write(
            v["name"],
            "interleaved-threads",
            f"{len(v['projects'])} interleaved project threads; the answer depends on one "
            "correction message from a single thread -- same failure mode as "
            "interleaved-threads, a different thread count/position.",
            messages,
            probes,
        )


# --- correction-of-earlier-answer: additional variants --------------------

_CORRECTION_VARIANTS = [
    dict(
        name="correction-address",
        original="My billing address is 12 Elm Street.",
        original_ack="Got it -- 12 Elm Street.",
        correction="Actually, my billing address changed -- it's now 88 Maple Avenue, not 12 Elm Street.",
        correction_ack="Understood -- updated to 88 Maple Avenue.",
        filler_topic="invoicing",
        before_count=8,
        after_count=8,
        question="What is the user's current billing address?",
        expected_answer="88 Maple Avenue",
    ),
    dict(
        name="correction-price",
        original="The quote for the project is $5,000.",
        original_ack="Noted -- $5,000 quote.",
        correction="I need to correct that -- the quote is actually $6,200 after adding the extra scope.",
        correction_ack="Updated -- $6,200.",
        filler_topic="scoping",
        before_count=6,
        after_count=10,
        question="What is the current quote for the project?",
        expected_answer="$6,200",
    ),
    dict(
        name="correction-deadline",
        original="The launch date is set for June 1st.",
        original_ack="June 1st, got it.",
        correction="Change of plans -- the launch date moved to June 15th.",
        correction_ack="Updated -- June 15th.",
        filler_topic="planning",
        before_count=12,
        after_count=5,
        question="What is the current launch date?",
        expected_answer="June 15th",
    ),
    dict(
        name="correction-phone-number",
        original="You can reach me at 555-0142.",
        original_ack="555-0142, noted.",
        correction="Sorry, I gave you the wrong number -- it's actually 555-0199.",
        correction_ack="Updated -- 555-0199.",
        filler_topic="support",
        before_count=9,
        after_count=9,
        question="What is the correct phone number to reach the user?",
        expected_answer="555-0199",
    ),
    dict(
        name="correction-meeting-room",
        original="Let's meet in Conference Room A.",
        original_ack="Conference Room A, got it.",
        correction="Room A is booked -- let's move the meeting to Conference Room C instead.",
        correction_ack="Updated -- Conference Room C.",
        filler_topic="scheduling",
        before_count=5,
        after_count=13,
        question="Which conference room is the meeting actually in?",
        expected_answer="Conference Room C",
    ),
    dict(
        name="correction-headcount",
        original="We're planning to hire 4 engineers this quarter.",
        original_ack="4 engineers this quarter, noted.",
        correction="Update -- the hiring plan was cut to 2 engineers this quarter, not 4.",
        correction_ack="Updated -- 2 engineers this quarter.",
        filler_topic="recruiting",
        before_count=14,
        after_count=6,
        question="How many engineers are we actually planning to hire this quarter?",
        expected_answer="2 engineers",
    ),
]


def build_correction_variants():
    for v in _CORRECTION_VARIANTS:
        messages = [msg("user", v["original"]), msg("assistant", v["original_ack"])]
        for i in range(v["before_count"]):
            messages += filler_exchange(v["filler_topic"], i)
        messages.append(msg("user", v["correction"]))
        messages.append(msg("assistant", v["correction_ack"]))
        correction_index = 2 + v["before_count"] * 2
        for i in range(v["before_count"], v["before_count"] + v["after_count"]):
            messages += filler_exchange(v["filler_topic"], i)
        messages.append(msg("user", v["question"]))

        probes = [probe(v["question"], [correction_index], v["expected_answer"])]
        write(
            v["name"],
            "correction-of-earlier-answer",
            "The user states a fact, then explicitly corrects it partway through the "
            "conversation -- same failure mode as correction-of-earlier-answer, a "
            "different subject/values combination.",
            messages,
            probes,
        )


# --- long-tool-output: additional variants (varying position/content) -----

_LONG_TOOL_OUTPUT_VARIANTS = [
    dict(
        name="long-tool-output-early-error",
        setup_question="Here's this morning's build log, can you tell me what failed?",
        line_template=lambda i: f"[INFO] step-{i:03d} compiled target 'lib{i}' successfully",
        error_position=6,
        error_line="[ERROR] step-006 failed: missing dependency 'libssl-dev' during linking",
        line_count=70,
        filler_topic="ci",
        filler_count=18,
        question="Which build step failed, and why?",
        expected_answer="step-006 failed due to a missing 'libssl-dev' dependency",
    ),
    dict(
        name="long-tool-output-late-error",
        setup_question="Here's the full test run output, what broke?",
        line_template=lambda i: f"[PASS] test_case_{i:03d} ({20 + i}ms)",
        error_position=95,
        error_line="[FAIL] test_case_095: AssertionError -- expected status 200, got 503",
        line_count=100,
        filler_topic="debugging",
        filler_count=20,
        question="Which test case failed, and what was the assertion error?",
        expected_answer="test_case_095 failed: expected status 200, got 503",
    ),
    dict(
        name="long-tool-output-deploy-log",
        setup_question="Here's the deployment log from last night, did anything go wrong?",
        line_template=lambda i: f"[INFO] instance-{i:03d} health check passed",
        error_position=50,
        error_line="[ERROR] instance-050 failed health check: connection refused on port 8080",
        line_count=90,
        filler_topic="ops",
        filler_count=14,
        question="Which instance failed its health check during deployment, and why?",
        expected_answer="instance-050 failed: connection refused on port 8080",
    ),
    dict(
        name="long-tool-output-db-query-log",
        setup_question="Here's the slow query log, what's the worst offender?",
        line_template=lambda i: f"[QUERY] SELECT * FROM orders WHERE id={i} -- {5 + (i % 4)}ms",
        error_position=63,
        error_line="[QUERY] SELECT * FROM orders JOIN users ON users.id=orders.user_id -- 14200ms (missing index)",
        line_count=75,
        filler_topic="database",
        filler_count=16,
        question="Which query was the slowest, and why?",
        expected_answer="the orders/users join at 14200ms, due to a missing index",
    ),
    dict(
        name="long-tool-output-security-scan",
        setup_question="Here's the dependency security scan output, anything critical?",
        line_template=lambda i: f"[OK] package-{i:03d} no known vulnerabilities",
        error_position=30,
        error_line="[CRITICAL] package-030 'legacy-parser' has CVE-2024-99999: remote code execution",
        line_count=60,
        filler_topic="compliance",
        filler_count=12,
        question="Which package has a critical vulnerability, and what is it?",
        expected_answer="'legacy-parser' has CVE-2024-99999, a remote code execution vulnerability",
    ),
]


def build_long_tool_output_variants():
    for v in _LONG_TOOL_OUTPUT_VARIANTS:
        log_lines = [v["line_template"](i) for i in range(v["line_count"])]
        log_lines.insert(v["error_position"], v["error_line"])
        tool_output = "\n".join(log_lines)

        messages = [msg("user", v["setup_question"]), msg("assistant", tool_output)]
        for i in range(v["filler_count"]):
            messages += filler_exchange(v["filler_topic"], i)
        messages.append(msg("user", v["question"]))

        probes = [probe(v["question"], [1], v["expected_answer"])]
        write(
            v["name"],
            "long-tool-output",
            "A single large tool-output message contains one buried line that answers the "
            "eventual question -- same failure mode as long-tool-output, a different "
            "position/content combination.",
            messages,
            probes,
        )


# --- pinned-instruction-under-pressure: additional variants ---------------

_PINNED_VARIANTS = [
    dict(
        name="pinned-under-pressure-json-only",
        instruction="Always respond with valid JSON only, no prose.",
        filler_topic="formatting",
        filler_count=28,
        question="What output format were you instructed to always use?",
        expected_answer="valid JSON only, no prose",
    ),
    dict(
        name="pinned-under-pressure-no-pii",
        instruction="Never include a customer's full name or email in a response, use their ID instead.",
        filler_topic="support",
        filler_count=35,
        question="What is the instruction about handling customer names and emails?",
        expected_answer="never include a customer's full name or email, use their ID instead",
    ),
    dict(
        name="pinned-under-pressure-tone",
        instruction="Keep every response under three sentences and avoid technical jargon.",
        filler_topic="documentation",
        filler_count=24,
        question="What length and tone instruction did the assistant receive?",
        expected_answer="under three sentences, avoiding technical jargon",
    ),
    dict(
        name="pinned-under-pressure-citation",
        instruction="Every factual claim must be followed by a citation in brackets, like [source].",
        filler_topic="research",
        filler_count=32,
        question="What citation instruction was the assistant given?",
        expected_answer="every factual claim must be followed by a bracketed citation",
    ),
    dict(
        name="pinned-under-pressure-currency",
        instruction="Always state monetary amounts in USD, converting if the user gives another currency.",
        filler_topic="finance",
        filler_count=27,
        question="What currency instruction was the assistant given?",
        expected_answer="always state amounts in USD, converting from other currencies",
    ),
]


def build_pinned_variants():
    for v in _PINNED_VARIANTS:
        messages = [msg("system", v["instruction"], pinned=True)]
        for i in range(v["filler_count"]):
            messages += filler_exchange(v["filler_topic"], i)
        messages.append(msg("user", v["question"]))

        probes = [probe(v["question"], [0], v["expected_answer"])]
        write(
            v["name"],
            "pinned-instruction-under-pressure",
            "A pinned system instruction sits at the start of a long, high-token "
            "conversation -- same failure mode as pinned-instruction-under-pressure, a "
            "different instruction/filler combination.",
            messages,
            probes,
        )


# --- multi-probe-mixed: additional variants (combining failure modes) -----

def build_multi_probe_drift_and_correction():
    messages = [
        msg("user", "We're targeting Kubernetes for orchestration, not plain Docker Compose."),
        msg("assistant", "Kubernetes it is."),
    ]
    for topic in ["helm charts", "ingress setup", "secrets management"]:
        for i in range(3):
            messages += filler_exchange(topic, i)
    messages.append(msg("user", "Correction -- we're actually going with Nomad instead of Kubernetes."))
    messages.append(msg("assistant", "Updated -- Nomad for orchestration."))
    correction_index = len(messages) - 2
    for i in range(3, 9):
        messages += filler_exchange("scaling", i)
    messages.append(msg("user", "Which orchestrator did we decide on, originally and now?"))

    probes = [
        probe(
            "Which orchestrator was originally proposed?",
            [0],
            "Kubernetes",
        ),
        probe(
            "Which orchestrator did we actually decide on after the correction?",
            [correction_index],
            "Nomad",
        ),
    ]
    write(
        "multi-probe-drift-and-correction",
        "correction-of-earlier-answer",
        "A topic-drift-style setup (early decision, unrelated filler) combined with a "
        "later correction of that same decision -- two probes check the original "
        "statement and the correction survive independently.",
        messages,
        probes,
    )


def build_multi_probe_interleaved_and_pinned():
    messages = [msg("system", "Always flag any security-related change explicitly.", pinned=True)]
    for i in range(10):
        for project in ["Atlas", "Nova"]:
            messages.append(msg("user", f"[{project}] update {i}: nothing new."))
            messages.append(msg("assistant", f"[{project}] Noted."))
    messages.append(msg("user", "[Atlas] Security update -- rotated the database credentials."))
    messages.append(msg("assistant", "[Atlas] Flagged: security-related change -- credentials rotated."))
    security_index = len(messages) - 2
    messages.append(msg("user", "What security change happened on Atlas, and what's your standing instruction?"))

    probes = [
        probe(
            "What security-related change happened on Project Atlas?",
            [security_index],
            "database credentials were rotated",
        ),
        probe(
            "What standing instruction was the assistant given?",
            [0],
            "always flag any security-related change explicitly",
        ),
    ]
    write(
        "multi-probe-interleaved-and-pinned",
        "pinned-instruction-under-pressure",
        "Two interleaved project threads combined with a pinned instruction -- two probes "
        "check the pinned instruction and one specific interleaved message both survive.",
        messages,
        probes,
    )


def build_multi_probe_tool_output_and_early_fact():
    log_lines = [f"[INFO] check-{i:03d} passed" for i in range(50)]
    log_lines.insert(22, "[ERROR] check-022 failed: disk usage at 97%, threshold is 90%")
    tool_output = "\n".join(log_lines)

    messages = [
        msg("user", "For context, this environment is named 'staging-west'."),
        msg("assistant", "Noted -- environment 'staging-west'."),
        msg("user", "Here's the monitoring check output, what failed?"),
        msg("assistant", tool_output),
    ]
    for i in range(14):
        messages += filler_exchange("monitoring", i)
    messages.append(msg("user", "Which environment had the failing check, and which check failed?"))

    probes = [
        probe("What is the environment named?", [0], "staging-west"),
        probe("Which check failed, and why?", [3], "check-022 failed: disk usage at 97%, over the 90% threshold"),
    ]
    write(
        "multi-probe-tool-output-and-early-fact",
        "long-tool-output",
        "An early-established fact (environment name) combined with a large tool-output "
        "message containing a buried failure -- two probes check both survive "
        "independently of each other.",
        messages,
        probes,
    )


def build_multi_probe_triple_correction():
    messages = [
        msg("system", "Always use metric units.", pinned=True),
        msg("user", "The package weighs 2kg."),
        msg("assistant", "2kg, noted."),
    ]
    for i in range(9):
        messages += filler_exchange("shipping", i)
    messages.append(msg("user", "Correction -- the package actually weighs 3.5kg after repacking."))
    messages.append(msg("assistant", "Updated -- 3.5kg."))
    weight_correction_index = len(messages) - 2
    for i in range(9, 15):
        messages += filler_exchange("shipping", i)
    messages.append(msg("user", "What's the package's current weight, and what unit system should you use?"))

    probes = [
        probe("What is the package's current weight?", [weight_correction_index], "3.5kg"),
        probe("What unit system was the assistant instructed to use?", [0], "metric"),
    ]
    write(
        "multi-probe-triple-correction",
        "correction-of-earlier-answer",
        "A pinned unit-system instruction combined with a mid-conversation weight "
        "correction -- two probes check the pinned instruction and the correction "
        "survive independently.",
        messages,
        probes,
    )


def build_multi_probe_drift_and_tool_output():
    log_lines = [f"[INFO] job-{i:03d} completed" for i in range(40)]
    log_lines.insert(18, "[ERROR] job-018 failed: authentication token expired mid-run")
    tool_output = "\n".join(log_lines)

    messages = [
        msg("user", "We're using Terraform for infrastructure, not raw CloudFormation."),
        msg("assistant", "Terraform it is."),
    ]
    for topic in ["state backend", "module structure"]:
        for i in range(4):
            messages += filler_exchange(topic, i)
    messages.append(msg("user", "Here's the job log from the nightly run, what failed?"))
    messages.append(msg("assistant", tool_output))
    tool_index = len(messages) - 1
    for i in range(8, 14):
        messages += filler_exchange("scheduling", i)
    messages.append(msg("user", "Which IaC tool are we using, and which job failed overnight?"))

    probes = [
        probe("Which infrastructure-as-code tool are we using?", [0], "Terraform"),
        probe(
            "Which job failed in the nightly run, and why?",
            [tool_index],
            "job-018 failed: authentication token expired mid-run",
        ),
    ]
    write(
        "multi-probe-drift-and-tool-output",
        "long-tool-output",
        "An early tooling decision combined with a large tool-output message containing "
        "a buried failure later in the conversation -- two probes check both survive "
        "independently.",
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

    build_early_establishment_variants()
    build_topic_drift_variants()
    build_interleaved_variants()
    build_correction_variants()
    build_long_tool_output_variants()
    build_pinned_variants()
    build_multi_probe_drift_and_correction()
    build_multi_probe_interleaved_and_pinned()
    build_multi_probe_tool_output_and_early_fact()
    build_multi_probe_triple_correction()
    build_multi_probe_drift_and_tool_output()
