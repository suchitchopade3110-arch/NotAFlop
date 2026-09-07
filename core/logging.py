"""
Structured logging (Phase 1, C2). Configures structlog once, at import
time, so `get_logger()` is safe to call from any module regardless of
whether the app's own lifespan ever runs (most unit tests import a
service module directly without starting FastAPI).

Routes through the standard library `logging` module rather than
replacing it (`logger_factory=structlog.stdlib.LoggerFactory()`,
`wrapper_class=structlog.stdlib.BoundLogger`) — every structlog call
still ends up as a normal stdlib LogRecord, so pytest's `caplog` fixture
(which hooks stdlib logging) keeps working unchanged, and modules that
haven't been migrated to structlog yet can keep using
`logging.getLogger(...)` directly with no compatibility shim needed.

The final render step is a small custom key=value formatter rather than
structlog's built-in KeyValueRenderer: this codebase's existing log lines
(services/gate.py, repositories/report_repository.py, etc.) already use
an unquoted `key=value` convention — e.g. `raw_verdict=go`, not
`raw_verdict='go'` — and several tests assert on that exact substring.
Matching it keeps every log line in the codebase visually and
mechanically consistent, migrated or not.

Consistent fields, bound wherever they're actually known rather than
threaded through every call site by hand:
  - request_id: bound per-HTTP-request by core.middleware.RequestIDMiddleware
  - session_id: bound in core.session.get_session_context, and explicitly
    at the top of orchestrator._run_pipeline (the founder-report pipeline
    runs as a detached background task by design — see orchestrator/graph.py's
    module docstring — so it binds its own session_id rather than
    inheriting request-scoped contextvars whose lifetime doesn't match).
  - agent_name / duration / status: passed explicitly as kwargs at the
    specific call sites that have them (e.g. services/groq_client.py's
    retry logging, orchestrator's wave1/wave2 completion logging).

Never log full pitch text (or, should this app ever collect them, email
addresses) at info level — see services/keyword_extractor.py, which logs
transcript_len instead of transcript content.
"""
import structlog


def _plain_kv_renderer(logger, method_name, event_dict) -> str:
    event = event_dict.pop("event", "")
    parts = [str(event)] if event else []
    parts.extend(f"{key}={value}" for key, value in event_dict.items())
    return " ".join(parts)


def configure_logging() -> None:
    """Idempotent — structlog.configure() just overwrites its own global
    config, so calling this more than once (e.g. once at import time here,
    once explicitly from main.py's lifespan for clarity) is harmless."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.format_exc_info,  # renders exc_info=True into a full traceback
            _plain_kv_renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.stdlib.get_logger(name)


configure_logging()
