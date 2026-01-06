"""Use case for searching the knowledge graph."""

from apps.backend.src.domain.services import kg_service


def execute(query: str) -> dict:
    """Return a minimal graph snapshot filtered by query."""
    nodes = [{"id": 1, "name": query}]
    snapshot = kg_service.build_snapshot(nodes, [])
    return {"graph": snapshot.__dict__, "report": kg_service.generate_report(snapshot)}
