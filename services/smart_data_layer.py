"""
Smart Data Layer
Runs all 5 data sources in parallel.
Each source is individually cached in Redis with 24hr TTL.
"""
import asyncio
from services import cache
from services.data_sources import google_trends, reddit, hacker_news, product_hunt, wellfound


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
    Returns a unified signals dict ready for the orchestrator.
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
        if isinstance(result, Exception):
            signals[name] = {"source": name, "status": "unavailable", "reason": f"live fetch failed: {result}"}
        else:
            signals[name] = result

    return {"keyword": keyword, "signals": signals}