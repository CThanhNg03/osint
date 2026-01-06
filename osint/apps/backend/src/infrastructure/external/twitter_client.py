"""Minimal Twitter client placeholder."""

from apps.backend.src.infrastructure.settings import settings


def search_recent(username: str) -> list[dict]:
    """Return recent tweets for a username (stubbed)."""
    if not settings.twitter_bearer_token:
        return []
    return [{"text": f"Recent post from {username}", "id": "1"}]
