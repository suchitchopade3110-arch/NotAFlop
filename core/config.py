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

# Input validation (C5). Applies uniformly to every transcript entry path
# — typed text, audio (post-Whisper), and any future video-transcript
# path — via core.validation.validate_transcript().
TRANSCRIPT_MAX_LENGTH: int = int(os.getenv("TRANSCRIPT_MAX_LENGTH", "5000"))

# CORS (C6) — see core/cors.py for the resolution rule (env-driven,
# localhost default only in development, fails loudly otherwise).
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
CORS_ALLOWED_ORIGINS_RAW: str = os.getenv("CORS_ALLOWED_ORIGINS", "")

# Scoring: WEIGHTS_VERSION now lives in services/gate.py, next to the WEIGHTS
# it versions, instead of here — stamped on every report at write time.

# ── Phase 2: living verdict / evidence log ───────────────────────────
# Marginal snapshot cost target (C1) — a re-run should cost roughly a
# quarter of a full report. Purely observability (services.log_service
# logs a warning above this, same non-gating spirit as report_cost_usd).
SNAPSHOT_COST_WARN_THRESHOLD_USD: float = float(os.getenv("SNAPSHOT_COST_WARN_THRESHOLD_USD", "0.20"))

# Re-run cadence for the scheduled snapshot worker (C1) — an idea is due
# for a scheduled re-run once its latest snapshot is this many days old.
SNAPSHOT_SCHEDULE_INTERVAL_DAYS: int = int(os.getenv("SNAPSHOT_SCHEDULE_INTERVAL_DAYS", "7"))

# Feature flag: whether main.py's lifespan starts the background
# scheduler loop that periodically sweeps due ideas/lapsed criteria.
# Off by default (and in tests) — the worker functions are always
# callable directly/on-demand (POST /v1/ideas/{id}/snapshots, the
# internal sweep functions) regardless of this flag.
SNAPSHOT_SCHEDULER_ENABLED: bool = os.getenv("SNAPSHOT_SCHEDULER_ENABLED", "false").lower() == "true"
SNAPSHOT_SCHEDULER_INTERVAL_SECONDS: int = int(os.getenv("SNAPSHOT_SCHEDULER_INTERVAL_SECONDS", str(6 * 60 * 60)))

# Manual force-re-run cap (B1's POST /v1/ideas/{id}/snapshots) — rate
# limited independently of the validation caps above (RATE_LIMIT_*).
SNAPSHOT_MANUAL_RERUN_MAX: int = int(os.getenv("SNAPSHOT_MANUAL_RERUN_MAX", "3"))
SNAPSHOT_MANUAL_RERUN_WINDOW_SECONDS: int = int(
    os.getenv("SNAPSHOT_MANUAL_RERUN_WINDOW_SECONDS", str(24 * 60 * 60))
)

# Progressive identity (A4).
SESSION_CLAIM_TOKEN_TTL_SECONDS: int = int(os.getenv("SESSION_CLAIM_TOKEN_TTL_SECONDS", "900"))  # 15 min
MAGIC_LINK_RATE_LIMIT_MAX: int = int(os.getenv("MAGIC_LINK_RATE_LIMIT_MAX", "5"))
MAGIC_LINK_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("MAGIC_LINK_RATE_LIMIT_WINDOW_SECONDS", str(60 * 60)))
FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

# Public share card (B2) — no-auth route, rate limited per ip so a card
# going viral (or an adversarial scraper) can't drive unbounded reads.
SHARE_CARD_RATE_LIMIT_MAX: int = int(os.getenv("SHARE_CARD_RATE_LIMIT_MAX", "60"))
SHARE_CARD_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("SHARE_CARD_RATE_LIMIT_WINDOW_SECONDS", str(60 * 60)))

# Idea/report retention for unclaimed (no account_id) ideas, in days —
# claimed ideas persist indefinitely (see A4).
UNCLAIMED_IDEA_TTL_DAYS: int = int(os.getenv("UNCLAIMED_IDEA_TTL_DAYS", "30"))
