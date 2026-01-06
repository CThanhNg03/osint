"""Use case for searching people."""

from apps.backend.src.infrastructure.external import person_client


def execute(query: str) -> dict:
    """Delegate search to the person client."""
    return person_client.search_people(query)
