"""
ContextShift quick start.

Run directly:

    python examples/quickstart.py

No API key or network access required -- this uses a trivial in-process
LLMProvider so the example runs end to end on its own. Swap in
contextshift.llm.GroqProvider (or any other LLMProvider) to use a real
model; see the comment at the bottom.
"""
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.summarization import Summarizer

# --- 1. Message is the framework's plain, framework-agnostic domain type. ---

conversation = [
    Message(role="user", content="What's the capital of France?", token_count=8),
    Message(role="assistant", content="Paris.", token_count=3),
    Message(role="user", content="And its population?", token_count=6),
    Message(role="assistant", content="Roughly 2.1 million in the city proper.", token_count=10),
    Message(role="user", content="Thanks -- one more: what's the currency?", token_count=9),
]

# --- 2. A strategy decides which messages fit inside a token budget. ---

budget = TokenBudget(max_tokens=100, safety_margin=10)
strategy = PinnedRecencyStrategy(recent_buffer=2)
result = strategy.build(conversation, budget)

print("Kept:    ", [m.content for m in result.messages])
print("Excluded:", [m.content for m in result.excluded])


# --- 3. An LLMProvider is anything with matching complete()/stream() ---
# --- methods -- a structural Protocol, no inheritance required. This  ---
# --- trivial example needs no network or API key.                    ---

class EchoProvider:
    def complete(self, messages, max_tokens=1024):
        return f"[{len(list(messages))} messages summarized]"

    def stream(self, messages, max_tokens=1024):
        yield self.complete(messages, max_tokens)


# --- 4. Summarizer is a domain service built on any LLMProvider. ---

summarizer = Summarizer(EchoProvider())
summary = summarizer.summarize(conversation)
print("Summary: ", summary)


# To use a real model instead of EchoProvider, swap in GroqProvider --
# same Summarizer, same PinnedRecencyStrategy, no other code changes:
#
#     import os
#     from contextshift.llm import GroqProvider
#
#     provider = GroqProvider(api_key=os.environ["GROQ_API_KEY"])
#     summarizer = Summarizer(provider)
#     print(summarizer.summarize(conversation))
