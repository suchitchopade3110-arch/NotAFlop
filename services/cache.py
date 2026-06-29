import hashlib
import json
import time

import redis.asyncio as aioredis

from core.config import REDIS_URL

TTL_SECONDS = 86400  # 24 hours

_client: aioredis.Redis | None = None
_redis_available = True
_memory_cache: dict[str, tuple[float, str]] = {}


async def get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _client


def make_key(source: str, keyword: str) -> str:
    h = hashlib.md5(keyword.lower().strip().encode()).hexdigest()[:10]
    return f"notaflop:{source}:{h}"


async def get_cached(source: str, keyword: str) -> dict | None:
    key = make_key(source, keyword)
    raw = None

    if _redis_available:
        try:
            client = await get_client()
            raw = await client.get(key)
        except Exception:
            await _disable_redis()

    if raw is None:
        cached = _memory_cache.get(key)
        if cached:
            expires_at, raw = cached
            if expires_at < time.time():
                _memory_cache.pop(key, None)
                raw = None

    if raw:
        return json.loads(raw)
    return None


async def set_cached(source: str, keyword: str, data: dict) -> None:
    key = make_key(source, keyword)
    raw = json.dumps(data)

    if _redis_available:
        try:
            client = await get_client()
            await client.setex(key, TTL_SECONDS, raw)
            return
        except Exception:
            await _disable_redis()

    _memory_cache[key] = (time.time() + TTL_SECONDS, raw)


async def close():
    global _client
    if _client:
        await _client.aclose()
        _client = None


async def _disable_redis() -> None:
    global _client, _redis_available
    _redis_available = False
    if _client:
        await _client.aclose()
        _client = None
