"""Repository classes wrapping database access."""

from sqlalchemy.orm import Session
from apps.backend.src.infrastructure.persistence import models


class AnalysisLogRepository:
    """Persist and retrieve analysis logs."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, title: str, summary: str | None = None) -> models.AnalysisLog:
        record = models.AnalysisLog(title=title, summary=summary)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record


class DocumentRepository:
    """Persist document metadata."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, filename: str, storage_path: str) -> models.DocumentRecord:
        record = models.DocumentRecord(filename=filename, storage_path=storage_path)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list(self) -> list[models.DocumentRecord]:
        return self.db.query(models.DocumentRecord).all()

    def get(self, document_id: int) -> models.DocumentRecord | None:
        return self.db.query(models.DocumentRecord).filter(models.DocumentRecord.id == document_id).first()

    def delete(self, document_id: int) -> None:
        self.db.query(models.DocumentRecord).filter(models.DocumentRecord.id == document_id).delete()
        self.db.commit()
