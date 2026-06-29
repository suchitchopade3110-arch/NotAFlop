"""
Google Trends — Apify scraper
STUB: returns realistic mock data.
To activate: set APIFY_API_KEY in .env and replace _fetch_live().
"""
import os
import httpx

APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
ACTOR_ID = "emastra~google-trends-scraper"


async def fetch(keyword: str) -> dict:
    """Returns trend trajectory for keyword."""
    # ── STUB ─────────────────────────────────────────────────
    return _stub(keyword)
    # ── LIVE (uncomment when key is ready) ───────────────────
    # return await _fetch_live(keyword)


def _stub(keyword: str) -> dict:
    return {
        "source": "google_trends",
        "keyword": keyword,
        "trend": "rising",           # rising | stable | declining
        "interest_over_time": [45, 50, 55, 60, 72, 80, 85],  # last 7 weeks
        "peak_month": "2026-05",
        "related_queries": [f"{keyword} app", f"{keyword} software", f"best {keyword}"],
    }


async def _fetch_live(keyword: str) -> dict:
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
    async with httpx.AsyncClient(timeout=60) as client:
        run = await client.post(
            url,
            headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
            json={"searchTerms": [keyword], "geo": "", "timeRange": "today 3-m"},
        )
        run.raise_for_status()
        run_id = run.json()["data"]["id"]

        # Poll for result (simplified)
        result_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"
        result = await client.get(result_url, headers={"Authorization": f"Bearer {APIFY_API_KEY}"})
        result.raise_for_status()
        items = result.json()

        return {
            "source": "google_trends",
            "keyword": keyword,
            "raw": items,
        }