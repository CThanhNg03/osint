"""Use case for crawling social content."""

from apps.backend.src.infrastructure.external import twitter_client


def execute(username: str) -> dict:
    """Return enriched posts for a user."""
    posts = twitter_client.search_recent(username)
    return {"username": username, "posts": posts}
