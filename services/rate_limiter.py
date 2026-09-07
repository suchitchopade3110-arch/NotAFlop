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
import time
from dataclasses import dataclass

from redis.exceptions import RedisError

from core.config import (
    RATE_LIMIT_IP_MAX,
    RATE_LIMIT_SESSION_MAX,
    RATE_LIMIT_WINDOW_SECONDS,
    SNAPSHOT_MANUAL_RERUN_MAX,
    SNAPSHOT_MANUAL_RERUN_WINDOW_SECONDS,
)
from core.logging import get_logger
from services.cache import get_client

logger = get_logger("notaflop.rate_limiter")

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
                    "rate_limit_redis_check_failed",
                    key=key, status="falling_back_to_memory", exc_info=True,
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
        logger.error("rate_limit_unexpected_failure", key=key, status="failing_open", exc_info=True)
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


async def check_snapshot_rerun_rate_limit(idea_id: str) -> RateLimitResult:
    """Independent of check_rate_limit's validation caps (constraint:
    'rate limited independently of validation') — a founder forcing a
    re-run on one idea's log doesn't touch their validation quota, and
    vice versa. Scoped per idea, not per session, so it caps cost on the
    idea itself regardless of who's driving it."""
    return await _check_one(
        "idea_snapshot",
        f"ratelimit:snapshot:{idea_id}",
        SNAPSHOT_MANUAL_RERUN_MAX,
        SNAPSHOT_MANUAL_RERUN_WINDOW_SECONDS,
    )
