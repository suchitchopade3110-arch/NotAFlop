"""
Product Hunt — PH API v2
STUB: returns realistic mock data.
To activate: set PRODUCT_HUNT_API_KEY in .env and replace _fetch_live().
"""
import os
import httpx

PH_API_KEY = os.getenv("PRODUCT_HUNT_API_KEY", "")
PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"


async def fetch(keyword: str) -> dict:
    return _stub(keyword)
    # return await _fetch_live(keyword)


def _stub(keyword: str) -> dict:
    return {
        "source": "product_hunt",
        "keyword": keyword,
        "launch_count": 7,              # products in this space
        "market_signal": "validated",   # validated | emerging | saturated | absent
        "top_products": [
            {"name": f"{keyword.title()} Pro", "upvotes": 842, "launched": "2025-11"},
            {"name": f"Quick{keyword.title()}", "upvotes": 431, "launched": "2025-08"},
            {"name": f"{keyword.title()}ly", "upvotes": 289, "launched": "2026-02"},
        ],
    }


async def _fetch_live(keyword: str) -> dict:
    query = """
    query($q: String!) {
      posts(first: 5, order: VOTES, search: $q) {
        edges {
          node { name tagline votesCount createdAt }
        }
      }
    }
    """
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            PH_GRAPHQL,
            headers={"Authorization": f"Bearer {PH_API_KEY}", "Content-Type": "application/json"},
            json={"query": query, "variables": {"q": keyword}},
        )
        res.raise_for_status()
        edges = res.json()["data"]["posts"]["edges"]

        return {
            "source": "product_hunt",
            "keyword": keyword,
            "launch_count": len(edges),
            "top_products": [
                {"name": e["node"]["name"], "upvotes": e["node"]["votesCount"]}
                for e in edges
            ],
        }