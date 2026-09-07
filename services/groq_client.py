"""
Groq client — the ONLY module allowed to talk to the Groq API. Every
agent, filter, and the keyword extractor routes through chat() (or
transcribe_audio() for Whisper) here, which is why the retry policy below
(Phase 1, C1) lives in exactly one place instead of being duplicated at
every call site.

Retry policy: exponential backoff with jitter via tenacity, retrying only
on rate limits (429), timeouts, and 5xx — never on auth (401/403) or
malformed-request errors (4xx other than 429), which won't succeed no
matter how many times they're retried. No cheaper-model fallback on
exhausted retries: silently downgrading an agent's model would change its
scoring behavior, which is exactly the failure mode per-agent score
anchoring exists to prevent (see services/gate.py) — an agent that can't
reach Groq fails honestly instead.

Total retry wall-clock for chat() is capped (3 attempts, 20s total
including backoff) specifically so a flaky Groq call can't blow the ~30s
P95 report-latency budget on its own — the per-call httpx timeout was
tightened from 20s to 10s to leave room for that budget rather than
letting a single attempt alone consume most of it. transcribe_audio() has
its own, more generous retry budget since /transcribe isn't on the
report-generation critical path.
"""
import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, stop_after_delay, wait_exponential_jitter

from core.config import GROQ_API_KEY, WHISPER_MODEL
from core.logging import get_logger
from services import cost_tracking

logger = get_logger("notaflop.groq_client")

GROQ_BASE = "https://api.groq.com/openai/v1"

_headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}


def _is_retryable_groq_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)):
        return True
    return False


def _log_retry(retry_state) -> None:
    agent_name = retry_state.kwargs.get("agent_name", "unknown")
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "groq_retry",
        agent=agent_name, attempt=retry_state.attempt_number, exception=exc, status="retrying",
    )


# chat(): tight budget, on the report-generation critical path.
_chat_retry = retry(
    retry=retry_if_exception(_is_retryable_groq_error),
    stop=stop_after_attempt(3) | stop_after_delay(20),
    wait=wait_exponential_jitter(initial=0.5, max=3, jitter=1),
    before_sleep=_log_retry,
    reraise=True,
)

# transcribe_audio(): more generous — /transcribe isn't part of the
# report-latency budget, and audio uploads legitimately take longer.
_transcribe_retry = retry(
    retry=retry_if_exception(_is_retryable_groq_error),
    stop=stop_after_attempt(2) | stop_after_delay(35),
    wait=wait_exponential_jitter(initial=1, max=5, jitter=1),
    before_sleep=_log_retry,
    reraise=True,
)


@_transcribe_retry
async def transcribe_audio(audio_bytes: bytes, filename: str = "pitch.webm", *, agent_name: str = "transcriber") -> str:
    """Send raw audio bytes to GROQ Whisper. Returns transcript string."""
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{GROQ_BASE}/audio/transcriptions",
            headers=_headers,
            files={"file": (filename, audio_bytes, "audio/webm")},
            data={"model": WHISPER_MODEL, "response_format": "json", "language": "en"},
        )
        res.raise_for_status()
        return res.json()["text"].strip()


@_chat_retry
async def chat(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 300,
    temperature: float | None = None,
    *,
    agent_name: str = "unknown",
) -> str:
    """Single-turn chat completion via GROQ.

    temperature is opt-in and omitted from the request by default, leaving
    Groq's own default in effect for callers that don't pass it — only
    callers that need deterministic output (e.g. Phase 1's pass/fail
    filter) should set it explicitly.

    agent_name is opt-in, purely for retry/observability logging (see
    _log_retry above) — it never affects the request sent to Groq.
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            f"{GROQ_BASE}/chat/completions",
            headers={**_headers, "Content-Type": "application/json"},
            json=payload,
        )
        if res.status_code >= 400:
            logger.error("groq_error", agent=agent_name, status=res.status_code, body=res.text)
        res.raise_for_status()
        body = res.json()

        # C3: token/cost logging — every call, tagged with agent_name (and
        # request_id/session_id via the bound contextvars already merged
        # into every structlog call, see core/logging.py).
        usage = body.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost_usd = cost_tracking.record_call(agent_name, model, prompt_tokens, completion_tokens)
        logger.info(
            "groq_call_cost",
            agent=agent_name, model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cost_usd=cost_usd, status="ok",
        )

        return body["choices"][0]["message"]["content"].strip()
