"""
Deep health check (Phase 1, C4). GET /health returns per-dependency
status + latency for Groq, MongoDB, Redis, and each of the 5 market-data
sources, plus one overall status.

Every check is bounded by CHECK_TIMEOUT_SECONDS and wrapped so one
dependency raising or hanging never takes the others down with it (never
cascading) — a check that errors or times out is reported "down" for
that dependency only; the endpoint itself still returns 200 with a full
body. The whole result is cached for HEALTH_CACHE_TTL_SECONDS so hitting
/health repeatedly doesn't hammer every dependency behind it on every call.

Data-source checks are network-reachability probes (a lightweight GET to
the source's own host, or "down: not configured" with no network call at
all when a required API key is missing) — not a full fetch(). This tells
you whether the network path to a source is up, the same honest
distinction B1/B2 already draw for a source that's never even attempted
a call vs. one that tried and failed; it deliberately does not exercise
each source's business logic (auth details, rate limits) — that's what
the SignalResult envelope on a real /validate call already surfaces.

Overall status:
  - "down": Groq is down — nothing in this product can score a pitch
    without it, so this is the one dependency whose failure is the whole
    app failing, not a degradation.
  - "degraded": Groq is fine but something else (Mongo, Redis, or any
    data source) isn't — the app keeps serving (Mongo/Redis both have
    documented fallback behavior; a data source failure already surfaces
    honestly per-source rather than blocking anything).
  - "ok": everything checked out.
"""
import asyncio
import time

import httpx

from core.config import GROQ_API_KEY
from services import cache, mongo
from services.data_sources import google_trends, product_hunt, reddit

CHECK_TIMEOUT_SECONDS = 3.0
HEALTH_CACHE_TTL_SECONDS = 30.0

_cached_result: dict | None = None
_cached_at: float = 0.0


async def _run_check(coro) -> dict:
    """Runs one dependency check, bounded and never raising — returns
    {status, latency_ms, reason}."""
    started = time.monotonic()
    try:
        status, reason = await asyncio.wait_for(coro, timeout=CHECK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        status, reason = "down", f"timed out after {CHECK_TIMEOUT_SECONDS}s"
    except Exception as exc:
        status, reason = "down", str(exc)
    latency_ms = round((time.monotonic() - started) * 1000, 1)
    result = {"status": status, "latency_ms": latency_ms}
    if reason:
        result["reason"] = reason
    return result


async def _check_groq() -> tuple[str, str | None]:
    if not GROQ_API_KEY:
        return "down", "GROQ_API_KEY not configured"
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
        res = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
        if res.status_code < 400:
            return "ok", None
        if res.status_code < 500:
            # Reached Groq, request itself rejected (e.g. bad key) — the
            # network path works, this is a config problem, not "down".
            return "degraded", f"HTTP {res.status_code}"
        return "down", f"HTTP {res.status_code}"


async def _check_mongo() -> tuple[str, str | None]:
    db = mongo.get_db()
    if db is None:
        return "down", "not connected"
    await db.command("ping")
    return "ok", None


async def _check_redis() -> tuple[str, str | None]:
    client = await cache.get_client()
    await client.ping()
    return "ok", None


async def _check_reachable(host: str) -> tuple[str, str | None]:
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
        await client.get(host)
        # Any HTTP response at all (2xx-5xx) proves DNS + TCP + TLS to
        # this host work — that's "reachable", regardless of status code.
        return "ok", None


async def _check_data_source(name: str, configured: bool, host: str | None) -> tuple[str, str | None]:
    if host is None:
        return "down", "no live implementation yet"
    if not configured:
        return "down", "not configured"
    return await _check_reachable(host)


async def _compute_health() -> dict:
    checks = {}
    checks["groq"] = await _run_check(_check_groq())
    checks["mongodb"] = await _run_check(_check_mongo())
    checks["redis"] = await _run_check(_check_redis())
    checks["google_trends"] = await _run_check(
        _check_data_source("google_trends", bool(google_trends.APIFY_API_KEY), "https://api.apify.com")
    )
    checks["hacker_news"] = await _run_check(_check_data_source("hacker_news", True, "https://hn.algolia.com"))
    checks["product_hunt"] = await _run_check(
        _check_data_source("product_hunt", bool(product_hunt.PH_API_KEY), "https://api.producthunt.com")
    )
    checks["reddit"] = await _run_check(
        _check_data_source(
            "reddit", bool(reddit.REDDIT_CLIENT_ID and reddit.REDDIT_CLIENT_SECRET), "https://www.reddit.com"
        )
    )
    checks["wellfound"] = await _run_check(_check_data_source("wellfound", True, None))

    if checks["groq"]["status"] == "down":
        overall = "down"
    elif all(c["status"] == "ok" for c in checks.values()):
        overall = "ok"
    else:
        overall = "degraded"

    return {"status": overall, "checks": checks}


async def get_health(*, use_cache: bool = True) -> dict:
    global _cached_result, _cached_at

    now = time.monotonic()
    if use_cache and _cached_result is not None and (now - _cached_at) < HEALTH_CACHE_TTL_SECONDS:
        return _cached_result

    result = await _compute_health()
    _cached_result = result
    _cached_at = now
    return result
