import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    SQLALCHEMY_DATABASE_URI = 'sqlite:///contextshift.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_TOKENS = 4000
    RECENT_BUFFER = 6
    TOKEN_SAFETY_MARGIN = 200
    GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.1-8b-instant"
