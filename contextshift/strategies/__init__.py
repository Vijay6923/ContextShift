"""
Context-management strategies.

The heart of the framework: a common ContextStrategy interface plus
concrete strategies (starting with the pinned/recency-window policy
carried over from the original application) that select which messages
to send to the LLM under a token budget. New strategies are added here
by implementing the interface and registering with the strategy
registry, without modifying any existing strategy or the application
that consumes them.
"""
