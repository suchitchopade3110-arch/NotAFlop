import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# Models
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")
FILTER_MODEL = os.getenv("FILTER_MODEL", "llama-3.1-8b-instant")
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "llama-3.3-70b-versatile")
REASONING_MODEL = os.getenv("REASONING_MODEL", "deepseek-r1-distill-llama-70b")

# Limits
FILTER_MAX_TOKENS = 300
AUDIO_MAX_BYTES = 10 * 1024 * 1024
