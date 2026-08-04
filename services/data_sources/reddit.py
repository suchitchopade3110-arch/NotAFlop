"""
Reddit — PRAW (official API)
STUB: returns realistic mock data.
To activate: set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in .env and replace _fetch_live().
"""
import os

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = "notaflop-validator/0.1"


async def fetch(keyword: str) -> dict:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return {"source": "reddit", "status": "unavailable", "reason": "REDDIT_CLIENT_ID/SECRET not configured"}
    try:
        return await _fetch_live(keyword)
    except Exception as e:
        return {"source": "reddit", "status": "unavailable", "reason": f"live fetch failed: {e}"}


def _stub(keyword: str) -> dict:
    return {
        "source": "reddit",
        "keyword": keyword,
        "post_count": 142,
        "pain_frequency": "high",       # high | medium | low
        "top_subreddits": ["r/startups", "r/entrepreneur", "r/SaaS"],
        "sample_posts": [
            {"title": f"I hate that {keyword} is so hard to manage", "upvotes": 312, "comments": 89},
            {"title": f"Anyone built a tool for {keyword}?", "upvotes": 204, "comments": 61},
            {"title": f"Why is {keyword} still broken in 2026?", "upvotes": 178, "comments": 44},
        ],
        "sentiment": "frustrated",       # frustrated | neutral | positive
    }


async def _fetch_live(keyword: str) -> dict:
    import asyncpraw  # pip install asyncpraw

    reddit = asyncpraw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    posts = []
    subreddits = set()
    async for submission in reddit.subreddit("all").search(keyword, limit=25, sort="relevance"):
        posts.append({
            "title": submission.title,
            "upvotes": submission.score,
            "comments": submission.num_comments,
        })
        subreddits.add(f"r/{submission.subreddit.display_name}")

    await reddit.close()

    return {
        "source": "reddit",
        "keyword": keyword,
        "post_count": len(posts),
        "top_subreddits": list(subreddits)[:5],
        "sample_posts": posts[:3],
    }