"""
Magic-link claim tokens (A4) — single-use, short-TTL, stored in Redis
rather than Mongo: an ephemeral bearer credential doesn't belong in a
durable collection, and Redis's native TTL is exactly the right
primitive for "expires on its own, no sweep needed." Mirrors
services/cache.py's client/fallback idiom (in-memory fallback if Redis is
down) and services/rate_limiter.py's fail-open philosophy: a down Redis
degrades rate-limiting and token storage rather than blocking the claim
flow outright.
"""
import json
import time

from core.config import MAGIC_LINK_RATE_LIMIT_MAX, MAGIC_LINK_RATE_LIMIT_WINDOW_SECONDS, SESSION_CLAIM_TOKEN_TTL_SECONDS
from core.ids import generate_magic_link_token
from core.logging import get_logger
from services.cache import get_client

logger = get_logger("notaflop.auth_tokens")

_TOKEN_KEY_PREFIX = "notaflop:magiclink:token:"
_RATE_KEY_PREFIX = "notaflop:magiclink:rate:"

_memory_tokens: dict[str, dict] = {}
_memory_rate: dict[str, list[float]] = {}
_redis_available = True


async def _disable_redis() -> None:
    global _redis_available
    _redis_available = False


async def check_and_record_rate_limit(scope: str, key: str) -> bool:
    """Fixed-window cap (per email, per ip — routers/v1_auth.py checks
    both). Fails open on any Redis error: an infra bug must never block
    a legitimate claim, it just stops protecting the email provider from
    abuse for the duration of the outage."""
    global _redis_available
    rate_key = f"{_RATE_KEY_PREFIX}{scope}:{key}"

    try:
        if _redis_available:
            client = await get_client()
            count = await client.incr(rate_key)
            if count == 1:
                await client.expire(rate_key, MAGIC_LINK_RATE_LIMIT_WINDOW_SECONDS)
            return count <= MAGIC_LINK_RATE_LIMIT_MAX
    except Exception:
        logger.error("magic_link_rate_limit_redis_failed", status="falling_back_to_memory", exc_info=True)
        await _disable_redis()

    now = time.time()
    cutoff = now - MAGIC_LINK_RATE_LIMIT_WINDOW_SECONDS
    entries = _memory_rate.setdefault(rate_key, [])
    entries[:] = [t for t in entries if t > cutoff]
    entries.append(now)
    return len(entries) <= MAGIC_LINK_RATE_LIMIT_MAX


async def issue_token(email: str, session_id: str) -> str:
    global _redis_available
    token = generate_magic_link_token()
    key = f"{_TOKEN_KEY_PREFIX}{token}"
    payload = json.dumps({"email": email, "session_id": session_id})

    try:
        if _redis_available:
            client = await get_client()
            await client.setex(key, SESSION_CLAIM_TOKEN_TTL_SECONDS, payload)
            return token
    except Exception:
        logger.error("magic_link_issue_redis_failed", status="falling_back_to_memory", exc_info=True)
        await _disable_redis()

    _memory_tokens[key] = {"expires_at": time.time() + SESSION_CLAIM_TOKEN_TTL_SECONDS, "payload": payload}
    return token


async def redeem_token(token: str) -> dict | None:
    """Single-use: the token is deleted on read regardless of outcome, so
    a leaked or replayed token can never be redeemed twice. Returns None
    for a missing, expired, or already-redeemed token."""
    global _redis_available
    key = f"{_TOKEN_KEY_PREFIX}{token}"
    raw = None

    try:
        if _redis_available:
            client = await get_client()
            pipe = client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            results = await pipe.execute()
            raw = results[0]
    except Exception:
        logger.error("magic_link_redeem_redis_failed", status="falling_back_to_memory", exc_info=True)
        await _disable_redis()

    if raw is None:
        cached = _memory_tokens.pop(key, None)
        if cached and cached["expires_at"] >= time.time():
            raw = cached["payload"]

    if not raw:
        return None
    return json.loads(raw)
