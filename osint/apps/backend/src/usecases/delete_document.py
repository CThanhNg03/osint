"""Use case for deleting a document."""

from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence.repositories import DocumentRepository


def execute(db: Session, document_id: int) -> None:
    """Remove document metadata and file."""
    repo = DocumentRepository(db)
    repo.delete(document_id)
