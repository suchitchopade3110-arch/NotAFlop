"""
Rolling-window rate limiting (Redis sorted sets, in-memory fallback).

Two independent caps, both enforced by check_rate_limit():
  - session cap (primary, tight): RATE_LIMIT_SESSION_MAX per window.
  - ip cap (secondary, generous): RATE_LIMIT_IP_MAX per window — a cost
    backstop against one IP cycling through many session IDs to dodge
    the session cap.

A true rolling window (sorted-set members scored by request time,
trimmed on every check), not a fixed window — a client can't reset its
quota early by waiting for a fixed boundary to roll over.

Fails open on any unexpected error, not just a down Redis: an infra
bug must never block a legitimate free report generation.
"""
import logging
import time
from dataclasses import dataclass

from redis.exceptions import RedisError

from core.config import RATE_LIMIT_IP_MAX, RATE_LIMIT_SESSION_MAX, RATE_LIMIT_WINDOW_SECONDS
from services.cache import get_client

logger = logging.getLogger("notaflop.rate_limiter")

_redis_available = True
_memory_store: dict[str, list[float]] = {}


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float  # epoch seconds
    scope: str        # "session" | "ip"


async def _count_and_record_redis(key: str, window: int, now: float) -> int:
    client = await get_client()
    member = f"{now}:{time.time_ns()}"
    pipe = client.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return results[2]  # zcard


def _count_and_record_memory(key: str, window: int, now: float) -> int:
    entries = _memory_store.setdefault(key, [])
    cutoff = now - window
    entries[:] = [t for t in entries if t > cutoff]
    entries.append(now)
    return len(entries)


async def _check_one(scope: str, key: str, max_count: int, window: int) -> RateLimitResult:
    global _redis_available
    now = time.time()
    reset_at = now + window

    try:
        if _redis_available:
            try:
                count = await _count_and_record_redis(key, window, now)
            except RedisError:
                logger.error(
                    "Redis rate-limit check failed for %s — falling back to in-memory.",
                    key, exc_info=True,
                )
                _redis_available = False
                count = _count_and_record_memory(key, window, now)
        else:
            count = _count_and_record_memory(key, window, now)

        remaining = max(0, max_count - count)
        return RateLimitResult(
            allowed=count <= max_count, limit=max_count, remaining=remaining,
            reset_at=reset_at, scope=scope,
        )
    except Exception:
        logger.error(
            "Rate limiter failed unexpectedly for %s — failing open.", key, exc_info=True,
        )
        return RateLimitResult(
            allowed=True, limit=max_count, remaining=max_count, reset_at=reset_at, scope=scope,
        )


async def check_rate_limit(session_id: str, ip: str) -> RateLimitResult:
    """Checks the session cap first (primary); only checks/records the ip
    cap if the session cap passes. Returns the first result that blocks,
    or the session result if both pass."""
    session_result = await _check_one(
        "session", f"ratelimit:session:{session_id}", RATE_LIMIT_SESSION_MAX, RATE_LIMIT_WINDOW_SECONDS,
    )
    if not session_result.allowed:
        return session_result

    ip_result = await _check_one(
        "ip", f"ratelimit:ip:{ip}", RATE_LIMIT_IP_MAX, RATE_LIMIT_WINDOW_SECONDS,
    )
    if not ip_result.allowed:
        return ip_result

    return session_result
