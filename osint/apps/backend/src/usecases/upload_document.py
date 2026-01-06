"""Use case for uploading a document and storing metadata."""

from pathlib import Path
from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence.repositories import DocumentRepository
from apps.backend.src.domain.services import document_service


def execute(db: Session, filename: str, content: bytes, storage_dir: str = "./uploads") -> dict:
    """Persist file bytes to disk and register metadata."""
    Path(storage_dir).mkdir(parents=True, exist_ok=True)
    storage_path = str(Path(storage_dir) / filename)
    with open(storage_path, "wb") as f:
        f.write(content)
    repo = DocumentRepository(db)
    record = repo.add(filename=filename, storage_path=storage_path)
    text = document_service.parse_pdf(storage_path)
    summary = document_service.summarize_document(text)
    return {"id": record.id, "filename": filename, "summary": summary}
