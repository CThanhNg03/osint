"""Use case for retrieving a document."""

from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence.repositories import DocumentRepository
from apps.backend.src.common.errors import NotFoundError


def execute(db: Session, document_id: int) -> dict:
    """Fetch a document by id."""
    repo = DocumentRepository(db)
    record = repo.get(document_id)
    if not record:
        raise NotFoundError("Document not found")
    return {"id": record.id, "filename": record.filename, "path": record.storage_path}
