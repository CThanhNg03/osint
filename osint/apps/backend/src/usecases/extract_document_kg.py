"""Use case for extracting a knowledge graph from a document."""

from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence.repositories import DocumentRepository
from apps.backend.src.domain.services import document_service, kg_service


def execute(db: Session, document_id: int) -> dict:
    """Generate a simple graph snapshot from stored document text."""
    repo = DocumentRepository(db)
    record = repo.get(document_id)
    if not record:
        return {"graph": None}
    text = document_service.parse_pdf(record.storage_path)
    keywords = text.split()[:5]
    nodes = [{"id": idx, "name": word} for idx, word in enumerate(keywords)]
    snapshot = kg_service.build_snapshot(nodes, [])
    return {"graph": snapshot.__dict__}
