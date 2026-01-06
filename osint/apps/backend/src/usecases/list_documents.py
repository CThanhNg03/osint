"""Use case for listing documents."""

from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence.repositories import DocumentRepository


def execute(db: Session) -> list[dict]:
    """Return all document metadata records."""
    repo = DocumentRepository(db)
    return [{"id": doc.id, "filename": doc.filename} for doc in repo.list()]
