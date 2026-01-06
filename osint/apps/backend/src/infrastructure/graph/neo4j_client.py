"""Simple Neo4j client wrapper."""

from neo4j import GraphDatabase
from apps.backend.src.infrastructure.settings import settings


def get_neo4j_driver():
    """Create a Neo4j driver if credentials are configured."""
    if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
        return None
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
