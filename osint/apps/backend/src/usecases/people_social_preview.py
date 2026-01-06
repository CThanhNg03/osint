"""Use case for previewing social profile activity."""

from apps.backend.src.infrastructure.external import twitter_client


def execute(username: str) -> dict:
    """Return recent tweets as a preview."""
    return {"posts": twitter_client.search_recent(username)}
