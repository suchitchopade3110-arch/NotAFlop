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

# Internal/admin endpoints (e.g. GET /internal/verifier/stats). Empty by
# default, which fails the admin dependency closed (see
# core.dependencies.require_admin) rather than leaving an internal route
# open with no credential to check against.
ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")

# Cost estimation (C3) — approximate USD-per-million-token prices, for
# per-call/per-report cost *observability*, not billing-grade figures.
# Override via env if Groq's published pricing changes; unlisted models
# fall back to the GROQ_DEFAULT_* pair below.
GROQ_PRICE_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {
        "prompt": float(os.getenv("GROQ_PRICE_LLAMA_70B_PROMPT", "0.59")),
        "completion": float(os.getenv("GROQ_PRICE_LLAMA_70B_COMPLETION", "0.79")),
    },
    "llama-3.1-8b-instant": {
        "prompt": float(os.getenv("GROQ_PRICE_LLAMA_8B_PROMPT", "0.05")),
        "completion": float(os.getenv("GROQ_PRICE_LLAMA_8B_COMPLETION", "0.08")),
    },
}
GROQ_DEFAULT_PROMPT_PRICE_PER_M: float = float(os.getenv("GROQ_DEFAULT_PROMPT_PRICE_PER_M", "0.59"))
GROQ_DEFAULT_COMPLETION_PRICE_PER_M: float = float(os.getenv("GROQ_DEFAULT_COMPLETION_PRICE_PER_M", "0.79"))

# Scoring: WEIGHTS_VERSION now lives in services/gate.py, next to the WEIGHTS
# it versions, instead of here — stamped on every report at write time.
