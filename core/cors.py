"""
CORS origin resolution (Phase 1, C6). Origins come from
CORS_ALLOWED_ORIGINS (comma-separated) — never hardcoded, and never a
silent '*'/permissive fallback:

  - CORS_ALLOWED_ORIGINS set: always used, in every environment.
  - CORS_ALLOWED_ORIGINS unset AND ENVIRONMENT=development (the config
    default): falls back to http://localhost:3000, the local frontend
    dev origin.
  - CORS_ALLOWED_ORIGINS unset in any other ENVIRONMENT (staging,
    production, ...): fails loudly — raises CorsConfigurationError —
    rather than silently defaulting to localhost (which would never
    match a real deployed frontend's origin, quietly breaking every
    browser request) or to "*" (which would be a real vulnerability).

resolve_cors_origins() is called at import time by main.py, so a
misconfigured production deployment fails at process startup, not on the
first request.
"""
from core import config

_DEV_DEFAULT_ORIGIN = "http://localhost:3000"


class CorsConfigurationError(RuntimeError):
    pass


def resolve_cors_origins() -> list[str]:
    # Read from the core.config module at call time (not imported as bare
    # names at module load) so tests can monkeypatch core.config.ENVIRONMENT
    # / core.config.CORS_ALLOWED_ORIGINS_RAW and have it actually take effect.
    raw = config.CORS_ALLOWED_ORIGINS_RAW.strip()
    if raw:
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if not origins:
            raise CorsConfigurationError("CORS_ALLOWED_ORIGINS is set but contains no valid origins.")
        return origins

    if config.ENVIRONMENT == "development":
        return [_DEV_DEFAULT_ORIGIN]

    raise CorsConfigurationError(
        f"CORS_ALLOWED_ORIGINS must be set when ENVIRONMENT={config.ENVIRONMENT!r} — "
        "the localhost default only applies when ENVIRONMENT=development. "
        "Refusing to start with an undefined CORS policy rather than "
        "silently falling back to something permissive or wrong."
    )
