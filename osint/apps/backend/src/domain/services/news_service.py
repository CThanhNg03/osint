"""Domain service for news normalization."""

from typing import List, Dict


def normalize_items(items: List[Dict]) -> List[Dict]:
    """Ensure news items contain expected keys."""
    normalized: List[Dict] = []
    for item in items:
        normalized.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "source": item.get("source", "unknown"),
        })
    return normalized
