import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# MongoDB
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB: str = os.getenv("MONGODB_DB", "notaflop")

# Models
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")
FILTER_MODEL = os.getenv("FILTER_MODEL", "llama-3.1-8b-instant")
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "llama-3.3-70b-versatile")
REASONING_MODEL = os.getenv("REASONING_MODEL", "llama-3.3-70b-versatile")

# Limits
FILTER_MAX_TOKENS = 300
AUDIO_MAX_BYTES = 10 * 1024 * 1024

# Rate limiting (rolling windows, seconds)
RATE_LIMIT_SESSION_MAX = int(os.getenv("RATE_LIMIT_SESSION_MAX", "3"))
RATE_LIMIT_IP_MAX = int(os.getenv("RATE_LIMIT_IP_MAX", "15"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(24 * 60 * 60)))

# Verifier
VERIFIER_PENALTY_ENABLED: bool = os.getenv("VERIFIER_PENALTY_ENABLED", "false").lower() == "true"

# Scoring
WEIGHTS_VERSION = 2  # bump on any change to services/gate.py WEIGHTS
