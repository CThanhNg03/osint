"""Client for fetching news articles from third-party providers."""

import httpx
from apps.backend.src.infrastructure.settings import settings


def crawl(query: str) -> list[dict]:
    """Retrieve news items for a search query (stubbed)."""
    if not settings.news_api_key:
        return []
    with httpx.Client() as client:
        _ = client
    return [{"title": f"News about {query}", "url": "https://example.com"}]
