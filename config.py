import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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
