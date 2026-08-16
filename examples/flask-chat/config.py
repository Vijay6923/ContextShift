import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Vercel's file system is read-only except for /tmp/, so we must use /tmp/ for SQLite.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:////tmp/contextshift.db')
    # If DATABASE_URL starts with postgres://, replace with postgresql:// for SQLAlchemy
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_TOKENS = 4000
    RECENT_BUFFER = 6
    TOKEN_SAFETY_MARGIN = 200
    GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.1-8b-instant"
    # "gemini-2.5-flash" returns 404 ("no longer available to new users")
    # for API keys issued after Google's cutover to newer model names --
    # verified against a live key, not assumed. "gemini-flash-latest" is
    # Google's own forward-compatible alias (the one their error message
    # points to) and is what actually works today. Override here if your
    # account has access to a specific dated snapshot instead.
    GEMINI_MODEL = "gemini-flash-latest"
