"""
ContextShift quick start.

Run directly:

    python examples/quickstart.py

No API key or network access required -- FakeLLMProvider
(contextshift.testing) is an in-memory LLMProvider, so this runs end to
end on its own. Swap in contextshift.llm.GroqProvider (or any other
LLMProvider) to use a real model; see the comment at the bottom.
"""
from contextshift import ContextManager
from contextshift.core import Message, TokenBudget
from contextshift.strategies import PinnedRecencyStrategy
from contextshift.testing import FakeLLMProvider
from contextshift.tokenizers import HeuristicTokenizer

# --- 1. ContextManager: the recommended entry point for a chat turn. ---
#
# It composes a strategy (what to keep), a tokenizer (how to measure
# the new message), a budget (how much room there is), and a provider
# (how to actually get a reply) into one call.

manager = ContextManager(
    strategy=PinnedRecencyStrategy(recent_buffer=2),
    provider=FakeLLMProvider(complete_response="Roughly 2.1 million in the city proper."),
    tokenizer=HeuristicTokenizer(),
    budget=TokenBudget(max_tokens=100, safety_margin=10),
)

history = [
    Message(role="user", content="What's the capital of France?", token_count=8),
    Message(role="assistant", content="Paris.", token_count=3),
]

result = manager.chat(history, "And its population?")

print("Response:", result.response)
print("Context kept:    ", [m.content for m in result.context.messages])
print("Context excluded:", [m.content for m in result.context.excluded])


# --- 2. The pieces ContextManager composes are independently usable. ---
#
# A caller that only needs context selection -- no provider call at all
# -- can use a strategy directly. Message is the framework's plain,
# framework-agnostic domain type.

conversation = [
    Message(role="user", content="What's the capital of France?", token_count=8),
    Message(role="assistant", content="Paris.", token_count=3),
    Message(role="user", content="And its population?", token_count=6),
    Message(role="assistant", content="Roughly 2.1 million in the city proper.", token_count=10),
    Message(role="user", content="Thanks -- one more: what's the currency?", token_count=9),
]

budget = TokenBudget(max_tokens=100, safety_margin=10)
strategy = PinnedRecencyStrategy(recent_buffer=2)
selection = strategy.build(conversation, budget)

print()
print("Kept:    ", [m.content for m in selection.messages])
print("Excluded:", [m.content for m in selection.excluded])


# To use a real model instead of FakeLLMProvider, swap in GroqProvider --
# same ContextManager, same PinnedRecencyStrategy, no other code changes:
#
#     import os
#     from contextshift.llm import GroqProvider
#
#     manager = ContextManager(
#         strategy=PinnedRecencyStrategy(recent_buffer=2),
#         provider=GroqProvider(api_key=os.environ["GROQ_API_KEY"]),
#         tokenizer=HeuristicTokenizer(),
#         budget=TokenBudget(max_tokens=4000, safety_margin=200),
#     )
#     result = manager.chat(history, "And its population?")
#     print(result.response)
