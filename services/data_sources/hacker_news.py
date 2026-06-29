"""
Hacker News — Algolia HN API (free, no key needed)
STUB: returns realistic mock data.
To activate: replace _fetch_live() call in fetch().
"""
import httpx

HN_ALGOLIA = "https://hn.algolia.com/api/v1/search"


async def fetch(keyword: str) -> dict:
    return _stub(keyword)
    # return await _fetch_live(keyword)


def _stub(keyword: str) -> dict:
    return {
        "source": "hacker_news",
        "keyword": keyword,
        "hit_count": 38,
        "founder_pain_signal": "medium",   # high | medium | low
        "sample_posts": [
            {"title": f"Ask HN: Best tools for {keyword}?", "points": 210, "comments": 94},
            {"title": f"Show HN: I built a {keyword} manager", "points": 183, "comments": 72},
            {"title": f"Why {keyword} tooling is still terrible", "points": 145, "comments": 58},
        ],
    }


async def _fetch_live(keyword: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            HN_ALGOLIA,
            params={"query": keyword, "tags": "story", "hitsPerPage": 20},
        )
        res.raise_for_status()
        data = res.json()

        hits = data.get("hits", [])
        return {
            "source": "hacker_news",
            "keyword": keyword,
            "hit_count": data.get("nbHits", 0),
            "sample_posts": [
                {"title": h.get("title"), "points": h.get("points", 0), "comments": h.get("num_comments", 0)}
                for h in hits[:3]
            ],
        }