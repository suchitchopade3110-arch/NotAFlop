"""
Wellfound — scraper (competitor map)
STUB: returns realistic mock data.
To activate: implement _fetch_live() with httpx + BeautifulSoup or Apify actor.
"""


async def fetch(keyword: str) -> dict:
    return _stub(keyword)
    # return await _fetch_live(keyword)


def _stub(keyword: str) -> dict:
    return {
        "source": "wellfound",
        "keyword": keyword,
        "startup_count": 23,
        "competitor_signal": "moderate",    # heavy | moderate | light | none
        "top_startups": [
            {"name": f"{keyword.title()}Base", "stage": "Seed", "employees": "11-50", "raised": "$2M"},
            {"name": f"Get{keyword.title()}", "stage": "Series A", "employees": "51-100", "raised": "$8M"},
            {"name": f"{keyword.title()}HQ", "stage": "Pre-seed", "employees": "1-10", "raised": "$500K"},
        ],
    }


async def _fetch_live(keyword: str) -> dict:
    # Placeholder for real scraper implementation
    # Options: Apify Wellfound actor OR httpx + BS4 with rotating proxies
    raise NotImplementedError("Wellfound live scraper not yet implemented.")