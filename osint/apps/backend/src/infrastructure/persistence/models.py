"""SQLAlchemy ORM models for persisted entities."""

from sqlalchemy import Column, Integer, String, Text
from apps.backend.src.infrastructure.persistence.database import Base


class AnalysisLog(Base):
    """Stores analysis metadata and raw logs."""

    __tablename__ = "analysis_logs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)


class DocumentRecord(Base):
    """Represents an uploaded document entry."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
