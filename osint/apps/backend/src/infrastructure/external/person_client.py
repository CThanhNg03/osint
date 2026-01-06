"""HTTP client for the person service."""

import httpx
from apps.backend.src.infrastructure.settings import settings


def search_people(query: str) -> dict:
    """Proxy a search request to the person service."""
    if not settings.person_service_url:
        return {"people": []}
    with httpx.Client() as client:
        resp = client.get(f"{settings.person_service_url}/search", params={"q": query})
        resp.raise_for_status()
        return resp.json()
