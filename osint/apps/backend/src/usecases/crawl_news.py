"""Use case orchestrating news crawling."""

from apps.backend.src.infrastructure.external import news_client
from apps.backend.src.domain.services.news_service import normalize_items


def execute(query: str) -> list[dict]:
    """Fetch and normalize news items for a query."""
    raw_items = news_client.crawl(query)
    return normalize_items(raw_items)
