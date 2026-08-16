"""
Minimal, dependency-free stand-in for the original application's
config.Config, providing exactly the constants the other legacy
fixture modules in this package (context_builder.py, summarizer.py,
token_manager.py) depend on.

The real config.Config (examples/flask-chat/config.py) also wires up
Flask, SQLAlchemy, and dotenv -- none of which any legacy fixture or
characterization test needs. GROQ_API_KEY defaults to an obviously-fake
placeholder rather than requiring a real environment variable: every
characterization test that exercises summarizer.py mocks requests.post,
so no real key is ever sent anywhere.
"""
import os


class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "test-key-not-real")
    GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.1-8b-instant"
    MAX_TOKENS = 4000
    RECENT_BUFFER = 6
    TOKEN_SAFETY_MARGIN = 200
