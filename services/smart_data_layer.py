"""
Smart Data Layer
Runs all 5 data sources in parallel.
Each source is individually cached in Redis with 24hr TTL.

B2: every source's raw output is normalized into the shared SignalResult
envelope (services.data_sources.result) before it leaves this module —
the adapters themselves are untouched, this is the wrapping layer the
Phase 1 B2 task describes.
"""
import asyncio
from services import cache
from services.data_sources import google_trends, reddit, hacker_news, product_hunt, wellfound
from services.data_sources.result import normalize_source_result


async def _fetch_with_cache(source_name: str, fetcher, keyword: str) -> dict:
    """Check cache first; fetch and cache on miss."""
    cached = await cache.get_cached(source_name, keyword)
    if cached:
        cached["_cached"] = True
        return cached

    data = await fetcher(keyword)
    if isinstance(data, dict) and data.get("status") != "unavailable":
        await cache.set_cached(source_name, keyword, data)
    return data


async def gather_signals(keyword: str) -> dict:
    """
    Fire all 5 sources in parallel.
    Returns a unified signals dict ready for the orchestrator — each
    source normalized to the shared SignalResult shape (status, payload,
    fetched_at, reason).
    """
    results = await asyncio.gather(
        _fetch_with_cache("google_trends", google_trends.fetch, keyword),
        _fetch_with_cache("reddit", reddit.fetch, keyword),
        _fetch_with_cache("hacker_news", hacker_news.fetch, keyword),
        _fetch_with_cache("product_hunt", product_hunt.fetch, keyword),
        _fetch_with_cache("wellfound", wellfound.fetch, keyword),
        return_exceptions=True,   # don't let one source failure kill the rest
    )

    signals = {}
    sources = ["google_trends", "reddit", "hacker_news", "product_hunt", "wellfound"]

    for name, result in zip(sources, results):
        signals[name] = normalize_source_result(name, result).model_dump(mode="json")

    return {"keyword": keyword, "signals": signals}